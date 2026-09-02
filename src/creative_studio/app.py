"""AI 创意工作台本地 HTTP 服务。"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sys
import traceback
import uuid
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .ai_creative import (
    AiCreativeConfigurationError,
    AiCreativeRequestError,
    NARRATIVE_TAG_KEYS,
    VISUAL_TAG_KEYS,
    generate_creative_recommendations,
    generate_visual_creative_recommendations,
    load_ai_creative_config,
    load_ai_creative_game_info,
    load_ai_visual_creative_config,
    normalize_creative_tags,
    recommendation_kind_for_script_type,
)
from .carousel import CarouselValidationError, normalize_visual_carousel_config
from .generation_models import CreativeGenerationRequest
from .generation_service import CreativeGenerationService
from .image_jobs import GptWebImageClient, ImageJobRunner, gateway_base_from_environment
from .repository import StudioDataError, StudioRepository
from .auth import AuthError, AuthRateLimitError, AuthService


ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"
TAG_OPTIONS_PATH = ROOT_DIR / "config" / "creative_tag_options.json"
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = DATA_DIR / "creative_studio.db"
IMAGES_DIR = DATA_DIR / "images"
UPLOADS_DIR = DATA_DIR / "uploads"


class StudioApplication:
    def __init__(self) -> None:
        self.repository = StudioRepository(DATABASE_PATH)
        self.auth = AuthService(self.repository, cookie_secure=os.environ.get("CREATIVE_STUDIO_COOKIE_SECURE", "0") == "1")
        bootstrap_username = os.environ.get("CREATIVE_STUDIO_BOOTSTRAP_USERNAME")
        bootstrap_password = os.environ.get("CREATIVE_STUDIO_BOOTSTRAP_PASSWORD")
        if not self.repository.list_users() and bootstrap_username and bootstrap_password:
            self.auth.init_admin(bootstrap_username, bootstrap_password)
        self.image_runner = ImageJobRunner(
            self.repository,
            IMAGES_DIR,
            GptWebImageClient(
                gateway_base_from_environment(),
                os.environ.get("WEB_ERP_AI_CONTROL_TOKEN", ""),
            ),
        )
        self.generation_service = CreativeGenerationService(
            self.repository,
            image_runner=self.image_runner,
        )

    @staticmethod
    def _fingerprint(project: dict[str, Any]) -> str:
        script_type = str(project.get("script_type") or "").strip()
        normalized_tags = normalize_creative_tags(project.get("creative_tags"))
        active_keys = VISUAL_TAG_KEYS if script_type == "展示类" else NARRATIVE_TAG_KEYS
        value: dict[str, Any] = {
            "script_type": script_type,
            "creative_tags": {
                key: sorted(normalized_tags[key])
                for key in active_keys
            },
            "task_type": str(project.get("task_type") or "").strip(),
            "task_description": str(project.get("task_description") or "").strip(),
            "product_evidence_summary": str(project.get("product_evidence_summary") or "").strip(),
            "aspect_ratio": str(project.get("aspect_ratio") or "").strip(),
        }
        if script_type == "展示类":
            value["visual_carousel"] = normalize_visual_carousel_config(project.get("creative_tags"))
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def history(self, project_id: int) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        if project is None:
            raise StudioDataError("项目不存在")
        kind = recommendation_kind_for_script_type(project["script_type"])
        result = self.repository.generation_history(project_id, kind, self._fingerprint(project))
        result.update({
            "success": True,
            "recommendation_kind": kind,
            "input_fingerprint": self._fingerprint(project),
            "adoption": project.get("adoption"),
        })
        return result

    def generate(self, project_id: int) -> dict[str, Any]:
        outcome = self.generation_service.generate(CreativeGenerationRequest(project_id=project_id))
        return outcome.history


APP = StudioApplication()


def load_tag_options() -> dict[str, Any]:
    """读取随版本发布的标签选项，不把 Excel 或外部路径暴露给浏览器。"""

    try:
        payload = json.loads(TAG_OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise StudioDataError("标签配置不存在或无法解析") from exc
    if not isinstance(payload, dict) or not payload.get("narrative") or not payload.get("visual"):
        raise StudioDataError("标签配置格式无效")
    return payload


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "CreativeStudio/0.1"

    def log_message(self, format_text: str, *args: Any) -> None:
        sys.stdout.write("%s - %s\n" % (self.log_date_time_string(), format_text % args))

    def _cookies(self) -> SimpleCookie:
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        return cookies

    def _session_cookie(self) -> str | None:
        morsel = self._cookies().get("creative_session")
        return morsel.value if morsel else None

    def _csrf_cookie(self) -> str | None:
        morsel = self._cookies().get("creative_csrf")
        return morsel.value if morsel else None

    def _context(self):
        return APP.auth.authenticate_session(self._session_cookie())

    def _require_auth(self, csrf: bool = False):
        context = APP.auth.authenticate_session(self._session_cookie(), self._csrf_cookie() if csrf else None)
        if context is None:
            self._json({"success": False, "error": "需要登录"}, HTTPStatus.UNAUTHORIZED)
            raise _ResponseHandled()
        return context

    def _require_admin(self, csrf: bool = False):
        context = self._require_auth(csrf)
        if context.user.get("role") != "admin":
            self._json({"success": False, "error": "需要管理员权限"}, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return context

    def _require_project_access(self, project_id: int, context) -> dict[str, Any]:
        project = APP.repository.get_project(project_id)
        if project is None:
            self._json({"success": False, "error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            raise _ResponseHandled()
        if context.user.get("role") != "admin" and project.get("owner_user_id") != context.user.get("id"):
            self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return project

    def _set_auth_cookies(self, session_token: str, csrf_token: str) -> None:
        secure = "; Secure" if APP.auth.cookie_secure else ""
        self._pending_cookies = [f"creative_session={session_token}; Path=/; HttpOnly; SameSite=Lax{secure}", f"creative_csrf={csrf_token}; Path=/; SameSite=Lax{secure}"]

    def _clear_auth_cookies(self) -> None:
        self._pending_cookies = ["creative_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax", "creative_csrf=; Path=/; Max-Age=0; SameSite=Lax"]

    def do_GET(self) -> None:
        try:
            self._get()
        except Exception as exc:
            self._error(exc)

    def do_POST(self) -> None:
        try:
            self._post()
        except Exception as exc:
            self._error(exc)

    def do_PUT(self) -> None:
        try:
            self._put()
        except Exception as exc:
            self._error(exc)

    def do_DELETE(self) -> None:
        try:
            self._delete()
        except Exception as exc:
            self._error(exc)

    def _get(self) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/api/health":
            self._json({"success": True, "service": "AI创意工作台"})
            return
        if path == "/api/auth/status":
            context = self._context()
            self._json({"success": True, "authenticated": context is not None,
                        "user": context.user if context else None,
                        "csrf_token": self._csrf_cookie() if context else None})
            return
        if path == "/api/auth/me":
            context = self._require_auth()
            self._json({"success": True, "user": context.user})
            return
        if path == "/api/admin/users":
            self._require_admin()
            self._json({"success": True, "users": APP.repository.list_users()})
            return
        self._require_auth()
        if path == "/api/tag-options":
            self._json({"success": True, "config": load_tag_options()})
            return
        if path == "/api/projects":
            context = self._context()
            keyword = parse_qs(parsed.query).get("search", [""])[0]
            projects = APP.repository.list_projects(keyword)
            if context.user.get("role") != "admin":
                projects = [p for p in projects if p.get("owner_user_id") == context.user.get("id")]
            self._json({"success": True, "projects": projects})
            return
        project_match = re.fullmatch(r"/api/projects/(\d+)", path)
        if project_match:
            context = self._context()
            self._require_project_access(int(project_match.group(1)), context)
            project = APP.repository.get_project(int(project_match.group(1)))
            if project is None:
                self._json({"success": False, "error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({"success": True, "project": project})
            return
        history_match = re.fullmatch(r"/api/projects/(\d+)/history", path)
        if history_match:
            context = self._context()
            self._require_project_access(int(history_match.group(1)), context)
            self._json(APP.history(int(history_match.group(1))))
            return
        status_match = re.fullmatch(r"/api/visual-items/(\d+)/status", path)
        if status_match:
            context = self._context()
            owner = APP.repository.get_visual_item_owner_id(int(status_match.group(1)))
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            item = APP.repository.visual_item(int(status_match.group(1)))
            if item is None:
                self._json({"success": False, "error": "图片任务不存在"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({
                    "success": True,
                    "item": {
                        "id": int(item["id"]),
                        "image_status": item["image_status"],
                        "image_url": f"/api/visual-items/{int(item['id'])}/image" if item["image_status"] == "success" else "",
                        "image_error": item["image_error"],
                    },
                })
            return
        image_match = re.fullmatch(r"/api/visual-items/(\d+)/image", path)
        if image_match:
            context = self._context()
            owner = APP.repository.get_visual_item_owner_id(int(image_match.group(1)))
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            image_path = APP.repository.image_path_for_item(int(image_match.group(1)))
            if image_path is None or not image_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._file(image_path, cache="no-store")
            return
        self._static(path)

    def _post(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/auth/login":
            data = self._read_json()
            result = APP.auth.login(str(data.get("username") or ""), str(data.get("password") or ""), self.client_address[0], self.headers.get("User-Agent", ""))
            self._set_auth_cookies(result.session_token, result.csrf_token)
            self._json({"success": True, "user": result.user, "csrf_token": result.csrf_token})
            return
        if path == "/api/auth/logout":
            context = self._require_auth(csrf=True)
            APP.auth.logout(self._session_cookie(), int(context.user["id"]))
            self._clear_auth_cookies()
            self._json({"success": True})
            return
        if path == "/api/auth/password":
            context = self._require_auth(csrf=True)
            data = self._read_json()
            user = APP.auth.change_password(int(context.user["id"]), str(data.get("current_password") or ""), str(data.get("new_password") or ""))
            self._clear_auth_cookies()
            self._json({"success": True, "user": user})
            return
        if path == "/api/admin/users":
            context = self._require_admin(csrf=True)
            data = self._read_json()
            user = APP.auth.create_user(int(context.user["id"]), str(data.get("username") or ""), str(data.get("password") or ""))
            self._json({"success": True, "user": user}, HTTPStatus.CREATED)
            return
        user_match = re.fullmatch(r"/api/admin/users/(\d+)/(disable|enable|reset-password)", path)
        if user_match:
            context = self._require_admin(csrf=True)
            target_id, action = int(user_match.group(1)), user_match.group(2)
            if action == "reset-password":
                user, temporary_password = APP.auth.reset_user_password(int(context.user["id"]), target_id)
                self._json({"success": True, "user": user, "temporary_password": temporary_password})
            else:
                user = APP.auth.set_user_active(int(context.user["id"]), target_id, action == "enable")
                self._json({"success": True, "user": user})
            return
        self._require_auth(csrf=True)
        if path == "/api/projects":
            data = self._read_json()
            context = self._context()
            project = APP.repository.create_project(data.get("name", "未命名创意"), data.get("script_type", "展示类"), int(context.user["id"]))
            self._json({"success": True, "project": project}, HTTPStatus.CREATED)
            return
        generate_match = re.fullmatch(r"/api/projects/(\d+)/generate", path)
        if generate_match:
            self._require_project_access(int(generate_match.group(1)), self._context())
            self._json(APP.generate(int(generate_match.group(1))))
            return
        adopt_match = re.fullmatch(r"/api/projects/(\d+)/adopt", path)
        if adopt_match:
            project_id = int(adopt_match.group(1))
            self._require_project_access(project_id, self._context())
            data = self._read_json()
            if data.get("recommendation_kind") == "narrative":
                snapshot = APP.repository.adopt_narrative(
                    project_id, int(data.get("generation_id") or 0), int(data.get("item_index") or 0)
                )
            else:
                snapshot = APP.repository.adopt_visual(project_id, int(data.get("item_id") or 0))
            self._json({"success": True, "snapshot": snapshot})
            return
        retry_match = re.fullmatch(r"/api/visual-items/(\d+)/retry", path)
        if retry_match:
            item_id = int(retry_match.group(1))
            if not APP.repository.retry_visual_item(item_id):
                raise StudioDataError("只有失败的图片可以重新生成")
            APP.image_runner.retry(item_id)
            self._json({"success": True})
            return
        upload_match = re.fullmatch(r"/api/projects/(\d+)/files", path)
        if upload_match:
            self._require_project_access(int(upload_match.group(1)), self._context())
            self._upload_file(int(upload_match.group(1)))
            return
        self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)

    def _put(self) -> None:
        context = self._require_auth(csrf=True)
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        self._require_project_access(int(match.group(1)), context)
        project = APP.repository.update_project(int(match.group(1)), self._read_json())
        self._json({"success": True, "project": project})

    def _delete(self) -> None:
        context = self._require_auth(csrf=True)
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        self._require_project_access(int(match.group(1)), context)
        deleted = APP.repository.delete_project(int(match.group(1)))
        self._json({"success": deleted})

    def _upload_file(self, project_id: int) -> None:
        size = int(self.headers.get("Content-Length") or 0)
        if size <= 0 or size > 25 * 1024 * 1024:
            raise StudioDataError("参考文件必须小于25MB")
        original_name = unquote(str(self.headers.get("X-File-Name") or "").strip())
        if not original_name:
            raise StudioDataError("参考文件名不能为空")
        suffix = Path(original_name).suffix[:16]
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        target_dir = (UPLOADS_DIR / str(project_id)).resolve()
        if UPLOADS_DIR.resolve() not in target_dir.parents:
            raise StudioDataError("参考文件目录无效")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / stored_name
        target.write_bytes(self.rfile.read(size))
        record = APP.repository.add_project_file(project_id, Path(original_name).name, stored_name, size)
        self._json({"success": True, "file": record}, HTTPStatus.CREATED)

    def _read_json(self) -> dict[str, Any]:
        size = int(self.headers.get("Content-Length") or 0)
        if size < 0 or size > 2 * 1024 * 1024:
            raise StudioDataError("请求内容过大")
        raw = self.rfile.read(size) if size else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise StudioDataError("请求内容不是有效JSON") from exc
        if not isinstance(value, dict):
            raise StudioDataError("请求内容必须是对象")
        return value

    def _json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        for cookie in getattr(self, "_pending_cookies", []):
            self.send_header("Set-Cookie", cookie)
        self._pending_cookies = []
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, cache: str = "public, max-age=300") -> None:
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else unquote(request_path.lstrip("/"))
        target = (STATIC_DIR / relative).resolve()
        if target != STATIC_DIR.resolve() and STATIC_DIR.resolve() not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            target = STATIC_DIR / "index.html"
        self._file(target, cache="no-cache")

    def _error(self, exc: Exception) -> None:
        if isinstance(exc, _ResponseHandled):
            return
        if isinstance(exc, AuthRateLimitError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.TOO_MANY_REQUESTS)
            return
        if isinstance(exc, AuthError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.UNAUTHORIZED)
            return
        if isinstance(exc, (StudioDataError, AiCreativeConfigurationError, AiCreativeRequestError)):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        traceback.print_exc()
        self._json({"success": False, "error": "服务处理失败，请查看启动窗口日志"}, HTTPStatus.INTERNAL_SERVER_ERROR)


class _ResponseHandled(Exception):
    """Internal control flow after an error response has been written."""


def run() -> None:
    host = str(os.environ.get("CREATIVE_STUDIO_HOST") or "127.0.0.1")
    port = int(os.environ.get("CREATIVE_STUDIO_PORT") or 8775)
    server = ThreadingHTTPServer((host, port), StudioHandler)
    APP.image_runner.start()
    print(f"AI创意工作台：http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        APP.image_runner.stop()
        server.server_close()


if __name__ == "__main__":
    run()
