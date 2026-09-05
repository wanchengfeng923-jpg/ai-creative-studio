"""AI 创意工作台本地 HTTP 服务。"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import re
import sys
import threading
import traceback
import uuid
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping
from urllib.parse import parse_qs, unquote, urlsplit

from .ai_v2.adapters.image_gateway import ImageGatewayAdapter
from .ai_v2.adapters.text_gateway import GatewayHttpTransport, TextGatewayAdapter
from .ai_v2.application import AiV2Application, AiV2ApplicationError
from .ai_v2.http_api import AiV2HttpApi
from .ai_v2.model_ports import ImageModelPort, TextModelPort
from .ai_v2.store import SqliteAiV2Store
from .auth import AuthError, AuthPermissionError, AuthRateLimitError, AuthService
from .project_projection import ProjectProjection
from .repository import StudioDataError, StudioRepository


ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"
TAG_OPTIONS_PATH = ROOT_DIR / "config" / "creative_tag_options.json"
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = DATA_DIR / "creative_studio.db"
IMAGES_DIR = DATA_DIR / "images"
UPLOADS_DIR = DATA_DIR / "uploads"


class StudioApplication:
    """Runtime dependency container owned by the production composition root."""

    def __init__(
        self,
        repository: StudioRepository,
        auth: AuthService,
        *,
        project_projection: ProjectProjection,
        uploads_dir: Path,
        ai_v2_application: AiV2Application | None = None,
        ai_v2_factory: Callable[[], AiV2Application] | None = None,
    ) -> None:
        self.repository = repository
        self.auth = auth
        self.project_projection = project_projection
        self.uploads_dir = Path(uploads_dir).resolve()
        self._ai_v2_application = ai_v2_application
        self._ai_v2_factory = ai_v2_factory
        self._ai_v2_api: AiV2HttpApi | None = None
        self._ai_v2_lock = threading.Lock()

    @property
    def ai_v2_application(self) -> AiV2Application | None:
        if self._ai_v2_application is None and self._ai_v2_factory is not None:
            with self._ai_v2_lock:
                if self._ai_v2_application is None:
                    self._ai_v2_application = self._ai_v2_factory()
        return self._ai_v2_application

    @property
    def ai_v2_api(self) -> AiV2HttpApi | None:
        application = self.ai_v2_application
        if application is not None and self._ai_v2_api is None:
            with self._ai_v2_lock:
                if self._ai_v2_api is None:
                    self._ai_v2_api = AiV2HttpApi(application)
        return self._ai_v2_api

def create_application(
    *,
    database_path: Path = DATABASE_PATH,
    images_dir: Path = IMAGES_DIR,
    uploads_dir: Path = UPLOADS_DIR,
    clock: Callable[[], str] | None = None,
    environment: MutableMapping[str, str] | None = None,
    ai_v2_text_model: TextModelPort | None = None,
    ai_v2_image_model: ImageModelPort | None = None,
) -> StudioApplication:
    """Build the application graph, allowing deterministic adapters in tests."""

    source = environment if environment is not None else os.environ
    project_projection = ProjectProjection()
    repository = StudioRepository(
        database_path,
        **({"clock": clock} if clock is not None else {}),
    )
    auth = AuthService(
        repository,
        cookie_secure=str(source.get("CREATIVE_STUDIO_COOKIE_SECURE") or "0") == "1",
    )
    bootstrap_username = source.get("CREATIVE_STUDIO_BOOTSTRAP_USERNAME")
    bootstrap_password = source.get("CREATIVE_STUDIO_BOOTSTRAP_PASSWORD")
    if not repository.list_users() and bootstrap_username and bootstrap_password:
        auth.init_admin(bootstrap_username, bootstrap_password)
    def create_ai_v2_application() -> AiV2Application:
        gateway_url = str(
            source.get("CREATIVE_STUDIO_AI_GATEWAY_URL") or "http://127.0.0.1:8780"
        ).strip()
        api_key = str(source.get("CREATIVE_STUDIO_AI_API_KEY") or "local-chatgpt-gateway").strip()
        model = str(source.get("CREATIVE_STUDIO_AI_MODEL") or "gpt-5-6-mini").strip()
        control_token = str(source.get("CREATIVE_STUDIO_AI_CONTROL_TOKEN") or "").strip()
        try:
            timeout_seconds = float(source.get("CREATIVE_STUDIO_AI_TIMEOUT_SECONDS") or 300)
        except (TypeError, ValueError):
            timeout_seconds = 300.0
        transport = GatewayHttpTransport(
            api_key=api_key,
            control_token=control_token,
            timeout_seconds=timeout_seconds,
        )
        live_enabled = str(source.get("CREATIVE_STUDIO_AI_V2_LIVE") or "0").strip() == "1"
        if ai_v2_text_model is not None:
            text_model = ai_v2_text_model
        elif live_enabled:
            text_model = TextGatewayAdapter(transport, base_url=gateway_url, model=model)
        else:
            from .ai_v2.application import CandidateTextModel

            text_model = CandidateTextModel()
        if ai_v2_image_model is not None:
            image_model = ai_v2_image_model
        elif live_enabled:
            image_model = ImageGatewayAdapter(transport, base_url=gateway_url)
        else:
            from .ai_v2.application import CandidateImageModel

            image_model = CandidateImageModel()
        return AiV2Application(
            SqliteAiV2Store(database_path),
            text_model=text_model,
            image_model=image_model,
            project_provider=repository.get_project,
        )

    return StudioApplication(
        repository,
        auth,
        project_projection=project_projection,
        uploads_dir=uploads_dir,
        ai_v2_factory=create_ai_v2_application,
    )


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

    @property
    def application(self) -> StudioApplication:
        application = getattr(self.server, "application", None)
        if not isinstance(application, StudioApplication):
            raise RuntimeError("HTTP server is missing its StudioApplication")
        return application

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
        morsel = self._cookies().get("studio_session")
        return morsel.value if morsel else None

    def _csrf_cookie(self) -> str | None:
        morsel = self._cookies().get("studio_csrf")
        return morsel.value if morsel else None

    def _context(self):
        return self.application.auth.authenticate_session(self._session_cookie())

    def _require_auth(self, csrf: bool = False, allow_password_change: bool = False):
        context = self.application.auth.authenticate_session(
            self._session_cookie(), self._csrf_cookie() if csrf else None
        )
        if context is None:
            self._json({"success": False, "error": "需要登录"}, HTTPStatus.UNAUTHORIZED)
            raise _ResponseHandled()
        if context.user.get("must_change_password") and not allow_password_change:
            self._json({"success": False, "error": "请先修改密码"}, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return context

    def _require_admin(self, csrf: bool = False):
        context = self._require_auth(csrf)
        if context.user.get("role") != "admin":
            self._json({"success": False, "error": "需要管理员权限"}, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return context

    def _require_project_access(self, project_id: int, context) -> dict[str, Any]:
        project = self.application.repository.get_project(project_id)
        if project is None:
            self._json({"success": False, "error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            raise _ResponseHandled()
        if context.user.get("role") != "admin" and project.get("owner_user_id") != context.user.get("id"):
            self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return project

    def _v2_application(self) -> AiV2Application:
        application = self.application.ai_v2_application
        if application is None:
            raise RuntimeError("AI v2 application is not configured")
        return application

    def _v2_api_error(self, exc: AiV2ApplicationError) -> None:
        status = HTTPStatus.NOT_FOUND if exc.error_code.endswith("_not_found") else HTTPStatus.BAD_REQUEST
        self._json({
            "error_code": exc.error_code,
            "phase": exc.phase,
            "retryable": exc.retryable,
            "trace_id": uuid.uuid4().hex,
            "field_path": exc.field_path,
        }, status)

    def _require_v2_auth(self, csrf: bool = False):
        context = self.application.auth.authenticate_session(self._session_cookie())
        if context is None:
            self._json({
                "error_code": "unauthorized",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.UNAUTHORIZED)
            raise _ResponseHandled()
        csrf_cookie = self._csrf_cookie() if csrf else None
        csrf_header = self.headers.get("X-CSRF-Token") if csrf else None
        if csrf and (
            not csrf_cookie
            or not isinstance(csrf_header, str)
            or not hmac.compare_digest(csrf_cookie, csrf_header)
        ):
            self._json({
                "error_code": "csrf_invalid",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        if csrf:
            context = self.application.auth.authenticate_session(self._session_cookie(), csrf_cookie)
        if context is None:
            self._json({
                "error_code": "unauthorized",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.UNAUTHORIZED)
            raise _ResponseHandled()
        if context.user.get("must_change_password"):
            self._json({
                "error_code": "password_change_required",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.FORBIDDEN)
            raise _ResponseHandled()
        return context

    def _require_v2_project_access(self, project_id: int, context) -> bool:
        project = self.application.repository.get_project(project_id)
        if project is None:
            self._json({
                "error_code": "project_not_found",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.NOT_FOUND)
            return False
        if context.user.get("role") != "admin" and project.get("owner_user_id") != context.user.get("id"):
            self._json({
                "error_code": "forbidden",
                "phase": "authorization",
                "retryable": False,
                "trace_id": uuid.uuid4().hex,
            }, HTTPStatus.FORBIDDEN)
            return False
        return True

    def _require_v2_route_access(self, path: str, context) -> bool:
        """Resolve a v2 resource to its project before exposing its public DTO."""

        project_match = re.fullmatch(r"/api/v2/projects/(\d+)/(?:generate|history|adopt|adoption)", path)
        try:
            if project_match:
                return self._require_v2_project_access(int(project_match.group(1)), context)
            run_match = re.fullmatch(r"/api/v2/runs/(\d+)", path)
            if run_match:
                return self._require_v2_project_access(self._v2_application().project_id_for_run(int(run_match.group(1))), context)
            scheme_match = re.fullmatch(r"/api/v2/schemes/(\d+)/(?:image|frames/\d+/image)", path)
            if scheme_match:
                return self._require_v2_project_access(self._v2_application().project_id_for_scheme(int(scheme_match.group(1))), context)
            attempt_match = re.fullmatch(r"/api/v2/image-attempts/(\d+)(?:/image)?", path)
            if attempt_match:
                return self._require_v2_project_access(self._v2_application().project_id_for_attempt(int(attempt_match.group(1))), context)
        except AiV2ApplicationError as exc:
            self._v2_api_error(exc)
            return False
        return True

    def _dispatch_v2(self, method: str, path: str, body: Mapping[str, Any] | None, context) -> None:
        if not self._require_v2_route_access(path, context):
            return
        image_match = re.fullmatch(r"/api/v2/image-attempts/(\d+)/image", path)
        if method == "GET" and image_match:
            try:
                content, mime_type = self._v2_application().image_bytes(int(image_match.group(1)))
            except AiV2ApplicationError as exc:
                self._v2_api_error(exc)
                return
            self._bytes(content, mime_type, cache="no-store")
            return
        api = self.application.ai_v2_api
        if api is None:
            raise RuntimeError("AI v2 HTTP API is not configured")
        status, payload = api.dispatch(method, path, body)
        self._json(payload, status)

    def _set_auth_cookies(self, session_token: str, csrf_token: str) -> None:
        secure = "; Secure" if self.application.auth.cookie_secure else ""
        self._pending_cookies = [f"studio_session={session_token}; Path=/; HttpOnly; SameSite=Lax{secure}", f"studio_csrf={csrf_token}; Path=/; SameSite=Strict{secure}"]

    def _clear_auth_cookies(self) -> None:
        self._pending_cookies = ["studio_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax", "studio_csrf=; Path=/; Max-Age=0; SameSite=Strict"]

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
        if path.startswith("/api/v2/"):
            self._dispatch_v2("GET", path, None, self._require_v2_auth())
            return
        if path == "/api/admin/users":
            self._require_admin()
            self._json({"success": True, "users": self.application.repository.list_users()})
            return
        if not path.startswith("/api/"):
            self._static(path)
            return
        self._require_auth()
        if path == "/api/tag-options":
            self._json({"success": True, "config": load_tag_options()})
            return
        if path == "/api/projects":
            context = self._context()
            keyword = parse_qs(parsed.query).get("search", [""])[0]
            projects = self.application.repository.list_projects(keyword)
            if context.user.get("role") != "admin":
                projects = [p for p in projects if p.get("owner_user_id") == context.user.get("id")]
            self._json({
                "success": True,
                "projects": [self.application.project_projection.summary(project) for project in projects],
            })
            return
        project_match = re.fullmatch(r"/api/projects/(\d+)", path)
        if project_match:
            context = self._context()
            self._require_project_access(int(project_match.group(1)), context)
            project = self.application.repository.get_project(int(project_match.group(1)))
            if project is None:
                self._json({"success": False, "error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({
                    "success": True,
                    "project": self.application.project_projection.project(project),
                })
            return
        self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)

    def _post(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/auth/login":
            data = self._read_json()
            result = self.application.auth.login(str(data.get("username") or ""), str(data.get("password") or ""), self.client_address[0], self.headers.get("User-Agent", ""))
            self._set_auth_cookies(result.session_token, result.csrf_token)
            self._json({"success": True, "user": result.user, "csrf_token": result.csrf_token})
            return
        if path == "/api/auth/logout":
            context = self._require_auth(csrf=True, allow_password_change=True)
            self.application.auth.logout(self._session_cookie(), int(context.user["id"]))
            self._clear_auth_cookies()
            self._json({"success": True})
            return
        if path == "/api/auth/password":
            context = self._require_auth(csrf=True, allow_password_change=True)
            data = self._read_json()
            user = self.application.auth.change_password(int(context.user["id"]), str(data.get("current_password") or ""), str(data.get("new_password") or ""))
            self._clear_auth_cookies()
            self._json({"success": True, "user": user})
            return
        if path == "/api/admin/users":
            context = self._require_admin(csrf=True)
            data = self._read_json()
            user = self.application.auth.create_user(int(context.user["id"]), str(data.get("username") or ""), str(data.get("password") or ""))
            self._json({"success": True, "user": user}, HTTPStatus.CREATED)
            return
        user_match = re.fullmatch(r"/api/admin/users/(\d+)/(disable|enable|reset-password)", path)
        if user_match:
            context = self._require_admin(csrf=True)
            target_id, action = int(user_match.group(1)), user_match.group(2)
            if action == "reset-password":
                user, temporary_password = self.application.auth.reset_user_password(int(context.user["id"]), target_id)
                self._json({"success": True, "user": user, "temporary_password": temporary_password})
            else:
                user = self.application.auth.set_user_active(int(context.user["id"]), target_id, action == "enable")
                self._json({"success": True, "user": user})
            return
        edit_match = re.fullmatch(r"/api/admin/users/(\d+)", path)
        if edit_match:
            context = self._require_admin(csrf=True)
            data = self._read_json()
            user = self.application.auth.update_user_username(int(context.user["id"]), int(edit_match.group(1)), str(data.get("username") or ""))
            self._json({"success": True, "user": user})
            return
        delete_match = re.fullmatch(r"/api/admin/users/(\d+)/delete", path)
        if delete_match:
            context = self._require_admin(csrf=True)
            self.application.auth.delete_user(int(context.user["id"]), int(delete_match.group(1)))
            self._json({"success": True})
            return
        if path.startswith("/api/v2/"):
            self._dispatch_v2("POST", path, self._read_json(), self._require_v2_auth(csrf=True))
            return
        self._require_auth(csrf=True)
        if path == "/api/projects":
            data = self._read_json()
            context = self._context()
            project = self.application.repository.create_project(data.get("name", "未命名创意"), data.get("script_type", "展示类"), int(context.user["id"]))
            self._json({
                "success": True,
                "project": self.application.project_projection.project(project),
            }, HTTPStatus.CREATED)
            return
        upload_match = re.fullmatch(r"/api/projects/(\d+)/files", path)
        if upload_match:
            self._require_project_access(int(upload_match.group(1)), self._context())
            self._upload_file(int(upload_match.group(1)))
            return
        self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)

    def _put(self) -> None:
        context = self._require_auth(csrf=True)
        edit_match = re.fullmatch(r"/api/admin/users/(\d+)", urlsplit(self.path).path)
        if edit_match:
            context = self._require_admin(csrf=True)
            data = self._read_json()
            user = self.application.auth.update_user_username(int(context.user["id"]), int(edit_match.group(1)), str(data.get("username") or ""))
            self._json({"success": True, "user": user})
            return
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        self._require_project_access(int(match.group(1)), context)
        project = self.application.repository.update_project(int(match.group(1)), self._read_json())
        self._json({
            "success": True,
            "project": self.application.project_projection.project(project),
        })

    def _delete(self) -> None:
        context = self._require_auth(csrf=True)
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        self._require_project_access(int(match.group(1)), context)
        deleted = self.application.repository.delete_project(int(match.group(1)))
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
        uploads_dir = self.application.uploads_dir
        target_dir = (uploads_dir / str(project_id)).resolve()
        if uploads_dir not in target_dir.parents:
            raise StudioDataError("参考文件目录无效")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / stored_name
        payload = self.rfile.read(size)
        target.write_bytes(payload)
        mime_type = mimetypes.guess_type(Path(original_name).name)[0] or "application/octet-stream"
        extraction_status = "complete" if mime_type.startswith("text/") or mime_type == "application/json" else "unsupported"
        safe_summary = ""
        if extraction_status == "complete":
            safe_summary = " ".join(payload[:8_000].decode("utf-8", errors="replace").split())[:2_000]
        record = self.application.repository.add_project_file(
            project_id,
            Path(original_name).name,
            stored_name,
            size,
            sha256=hashlib.sha256(payload).hexdigest(),
            mime_type=mime_type,
            extraction_status=extraction_status,
            safe_summary=safe_summary,
        )
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

    def _bytes(self, content: bytes, mime_type: str, cache: str = "public, max-age=300") -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(content)

    def _static(self, request_path: str) -> None:
        if request_path in {"/ai-v2", "/ai-v2/"}:
            self._file(STATIC_DIR / "ai-v2" / "index.html", cache="no-cache")
            return
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
        if isinstance(exc, AuthPermissionError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.FORBIDDEN)
            return
        if isinstance(exc, AuthError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.UNAUTHORIZED)
            return
        if isinstance(exc, StudioDataError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        traceback.print_exc()
        self._json({"success": False, "error": "服务处理失败，请查看启动窗口日志"}, HTTPStatus.INTERNAL_SERVER_ERROR)


class _ResponseHandled(Exception):
    """Internal control flow after an error response has been written."""


def run() -> None:
    host = str(os.environ.get("CREATIVE_STUDIO_HOST") or "127.0.0.1")
    port = int(os.environ.get("CREATIVE_STUDIO_PORT") or 8775)
    application = create_application()
    server = ThreadingHTTPServer((host, port), StudioHandler)
    server.application = application  # type: ignore[attr-defined]
    print(f"AI创意工作台：http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if application._ai_v2_application is not None:
            application._ai_v2_application.store.close()
        server.server_close()


if __name__ == "__main__":
    run()
