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
from .image_jobs import GptWebImageClient, ImageJobRunner, gateway_base_from_environment
from .repository import StudioDataError, StudioRepository


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
        self.image_runner = ImageJobRunner(
            self.repository,
            IMAGES_DIR,
            GptWebImageClient(
                gateway_base_from_environment(),
                os.environ.get("WEB_ERP_AI_CONTROL_TOKEN", ""),
            ),
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
        project = self.repository.get_project(project_id)
        if project is None:
            raise StudioDataError("项目不存在")
        if not str(project.get("task_description") or "").strip():
            raise StudioDataError("请先填写创意说明")
        tag_options = load_tag_options()
        kind = recommendation_kind_for_script_type(project["script_type"])
        carousel_config = None
        if kind == "visual":
            try:
                carousel_config = normalize_visual_carousel_config(
                    project.get("creative_tags"),
                    require_enabled=True,
                )
            except CarouselValidationError as exc:
                raise StudioDataError(str(exc)) from exc
        fingerprint = self._fingerprint(project)
        carousel_enabled = bool(carousel_config and carousel_config.get("enabled") == "是")
        schema_version = "visual.carousel.v1" if carousel_enabled else ("visual.v1" if kind == "visual" else "narrative.v1")
        reservation = self.repository.reserve_generation(project_id, kind, schema_version, fingerprint)
        try:
            if kind == "visual":
                result = generate_visual_creative_recommendations(
                    normalize_creative_tags(project["creative_tags"]),
                    config=load_ai_visual_creative_config(carousel=carousel_enabled),
                    task_type=project["task_type"],
                    task_description=project["task_description"],
                    aspect_ratio=project["aspect_ratio"],
                    product_evidence_summary=project["product_evidence_summary"],
                    reference_file_names=self.repository.reference_file_names(project_id),
                    carousel_config=carousel_config if carousel_enabled else None,
                    tag_catalog=tag_options,
                    conversation_id=reservation["conversation_id"],
                    parent_message_id=reservation["parent_message_id"],
                )
                item_ids = self.repository.complete_visual_generation(
                    reservation["id"], result, project["aspect_ratio"]
                )
                self.image_runner.enqueue(item_ids)
            else:
                game_info = load_ai_creative_game_info()
                result = generate_creative_recommendations(
                    normalize_creative_tags(project["creative_tags"]),
                    config=load_ai_creative_config(),
                    game_info=game_info.content,
                    task_type=project["task_type"],
                    task_description=project["task_description"],
                    script_type=project["script_type"],
                    conversation_id=reservation["conversation_id"],
                    parent_message_id=reservation["parent_message_id"],
                )
                self.repository.complete_narrative_generation(reservation["id"], result)
        except Exception as exc:
            self.repository.fail_generation(reservation["id"], str(exc))
            raise
        return self.history(project_id)


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
        if path == "/api/tag-options":
            self._json({"success": True, "config": load_tag_options()})
            return
        if path == "/api/projects":
            keyword = parse_qs(parsed.query).get("search", [""])[0]
            self._json({"success": True, "projects": APP.repository.list_projects(keyword)})
            return
        project_match = re.fullmatch(r"/api/projects/(\d+)", path)
        if project_match:
            project = APP.repository.get_project(int(project_match.group(1)))
            if project is None:
                self._json({"success": False, "error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({"success": True, "project": project})
            return
        history_match = re.fullmatch(r"/api/projects/(\d+)/history", path)
        if history_match:
            self._json(APP.history(int(history_match.group(1))))
            return
        status_match = re.fullmatch(r"/api/visual-items/(\d+)/status", path)
        if status_match:
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
            image_path = APP.repository.image_path_for_item(int(image_match.group(1)))
            if image_path is None or not image_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._file(image_path, cache="no-store")
            return
        self._static(path)

    def _post(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/projects":
            data = self._read_json()
            project = APP.repository.create_project(data.get("name", "未命名创意"), data.get("script_type", "展示类"))
            self._json({"success": True, "project": project}, HTTPStatus.CREATED)
            return
        generate_match = re.fullmatch(r"/api/projects/(\d+)/generate", path)
        if generate_match:
            self._json(APP.generate(int(generate_match.group(1))))
            return
        adopt_match = re.fullmatch(r"/api/projects/(\d+)/adopt", path)
        if adopt_match:
            project_id = int(adopt_match.group(1))
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
            self._upload_file(int(upload_match.group(1)))
            return
        self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)

    def _put(self) -> None:
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        project = APP.repository.update_project(int(match.group(1)), self._read_json())
        self._json({"success": True, "project": project})

    def _delete(self) -> None:
        match = re.fullmatch(r"/api/projects/(\d+)", urlsplit(self.path).path)
        if not match:
            self._json({"success": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
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
        if isinstance(exc, (StudioDataError, AiCreativeConfigurationError, AiCreativeRequestError)):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        traceback.print_exc()
        self._json({"success": False, "error": "服务处理失败，请查看启动窗口日志"}, HTTPStatus.INTERNAL_SERVER_ERROR)


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
