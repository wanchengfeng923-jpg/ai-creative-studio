"""AI 创意工作台本地 HTTP 服务。"""

from __future__ import annotations

import hashlib
import hmac
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
from typing import Any, Callable, Mapping, MutableMapping
from urllib.parse import parse_qs, unquote, urlsplit

from .ai_creative import (
    AiCreativeConfigurationError,
    AiCreativeQueueTimeoutError,
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
from .generation_models import (
    GenerationConflictError,
    GenerationInputError,
    GenerationNotFoundError,
    GenerationQueueTimeoutError,
    error_details,
)
from .generation_service import CreativeGenerationService
from .image_jobs import GptWebImageClient, ImageJobRunner, gateway_base_from_environment
from .model_client import HttpModelClient, ModelClient
from .public_projection import PublicResultMapper
from .prompt_registry import PromptRegistry, PromptRegistryError
from .reference_assets import FileReferenceAssetStore
from .observability import StructuredObservability
from .repository import StudioDataError, StudioRepository
from .auth import AuthError, AuthPermissionError, AuthRateLimitError, AuthService
from .ai_v2.adapters.image_gateway import ImageGatewayAdapter
from .ai_v2.adapters.text_gateway import GatewayHttpTransport, TextGatewayAdapter
from .ai_v2.application import AiV2Application, AiV2ApplicationError
from .ai_v2.http_api import AiV2HttpApi
from .ai_v2.model_ports import ImageModelPort, TextModelPort
from .ai_v2.store import SqliteAiV2Store


ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT_DIR / "static"
TAG_OPTIONS_PATH = ROOT_DIR / "config" / "creative_tag_options.json"
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = DATA_DIR / "creative_studio.db"
IMAGES_DIR = DATA_DIR / "images"
UPLOADS_DIR = DATA_DIR / "uploads"
PROMPT_REGISTRY_PATH = ROOT_DIR / "config" / "prompts" / "registry.json"


class StudioApplication:
    """Runtime dependency container owned by the production composition root."""

    def __init__(
        self,
        repository: StudioRepository,
        auth: AuthService,
        image_runner: Any,
        generation_service: CreativeGenerationService,
        *,
        public_mapper: PublicResultMapper,
        uploads_dir: Path,
        prompt_registry: PromptRegistry | None = None,
        ai_v2_application: AiV2Application | None = None,
        ai_v2_factory: Callable[[], AiV2Application] | None = None,
    ) -> None:
        self.repository = repository
        self.auth = auth
        self.image_runner = image_runner
        self.generation_service = generation_service
        self.public_mapper = public_mapper
        self.uploads_dir = Path(uploads_dir).resolve()
        self.prompt_registry = prompt_registry
        self._ai_v2_application = ai_v2_application
        self._ai_v2_factory = ai_v2_factory
        self._ai_v2_api: AiV2HttpApi | None = None

    @property
    def ai_v2_application(self) -> AiV2Application | None:
        if self._ai_v2_application is None and self._ai_v2_factory is not None:
            self._ai_v2_application = self._ai_v2_factory()
        return self._ai_v2_application

    @property
    def ai_v2_api(self) -> AiV2HttpApi | None:
        application = self.ai_v2_application
        if application is not None and self._ai_v2_api is None:
            self._ai_v2_api = AiV2HttpApi(application)
        return self._ai_v2_api

    @staticmethod
    def _load_model_client(environment: Mapping[str, str] | None = None) -> HttpModelClient | None:
        source = environment if environment is not None else os.environ
        api_url = str(source.get("WEB_ERP_AI_API_URL") or "http://127.0.0.1:8780/v1/chat/completions").strip()
        api_key = str(source.get("WEB_ERP_AI_API_KEY") or "local-chatgpt-gateway").strip()
        model = str(source.get("WEB_ERP_AI_MODEL") or "gpt-5-6-mini").strip()
        if not api_url or not api_key or not model:
            return None
        try:
            timeout_seconds = float(source.get("WEB_ERP_AI_TIMEOUT_SECONDS") or 30)
        except (TypeError, ValueError):
            timeout_seconds = 30.0
        return HttpModelClient(
            api_url=api_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _ensure_default_ai_environment(environment: MutableMapping[str, str] | None = None) -> None:
        """Allow direct ``python -m creative_studio.app`` startup to use the local gateway."""

        target = environment if environment is not None else os.environ

        defaults = {
            "WEB_ERP_AI_API_URL": "http://127.0.0.1:8780/v1/chat/completions",
            "WEB_ERP_AI_API_KEY": "local-chatgpt-gateway",
            "WEB_ERP_AI_MODEL": "gpt-5-6-mini",
            "WEB_ERP_AI_PROVIDER": "chatgpt-web",
            "WEB_ERP_AI_VISUAL_PROMPT_PATH": str(ROOT_DIR / "config" / "ai_visual_creative_prompt_v2.txt"),
            "WEB_ERP_AI_PROMPT_PATH": str(ROOT_DIR / "config" / "ai_creative_prompt_v5.txt"),
            "WEB_ERP_AI_TIMEOUT_SECONDS": "300",
        }
        for key, value in defaults.items():
            if not str(target.get(key) or "").strip():
                target[key] = value

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
            "reference_assets": [
                {
                    "name": str(item.get("original_name") or ""),
                    "sha256": str(item.get("sha256") or ""),
                    "mime_type": str(item.get("mime_type") or ""),
                    "size_bytes": int(item.get("size_bytes") or 0),
                    "extraction_status": str(item.get("extraction_status") or "pending"),
                    "safe_summary": str(item.get("safe_summary") or ""),
                }
                for item in (project.get("reference_files") or [])
                if isinstance(item, Mapping)
            ],
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
        # GenerationService is the canonical owner of snapshot normalization and
        # prompt metadata. Rebuild that snapshot here so history classification
        # uses exactly the same fingerprint as the generation write path.
        fingerprint = self.generation_service._build_snapshot(project).fingerprint
        result = self.public_mapper.history(
            self.repository.generation_history(project_id, kind, fingerprint),
            recommendation_kind=kind,
        )
        result.update({
            "success": True,
            "recommendation_kind": kind,
            "input_fingerprint": fingerprint,
            "adoption": self.public_mapper.adoption(project.get("adoption")),
        })
        return result

    def generate(self, project_id: int) -> dict[str, Any]:
        outcome = self.generation_service.generate(CreativeGenerationRequest(project_id=project_id))
        result = self.public_mapper.history(
            outcome.history,
            recommendation_kind=outcome.snapshot.kind,
        )
        result.update({
            "success": True,
            "recommendation_kind": outcome.snapshot.kind,
            "input_fingerprint": outcome.snapshot.fingerprint,
        })
        return result

    def select_visual_scheme(self, item_id: int) -> dict[str, Any]:
        mapper = getattr(self, "public_mapper", None) or PublicResultMapper()
        return mapper.display_scheme(self.generation_service.select_scheme(int(item_id)))

    def continue_visual_scheme(self, item_id: int) -> dict[str, Any]:
        result = self.generation_service.continue_scheme(int(item_id))
        if "operation" not in result:
            # Keep the explicit legacy/test seam readable while production uses
            # the operation coordinator above.
            return {"scheme": self.public_mapper.display_scheme(result)}
        return {
            "operation": self.public_mapper.carousel_operation(result["operation"]),
            "scheme": self.public_mapper.display_scheme(result["scheme"]),
        }

    def carousel_operation_status(self, item_id: int, operation_id: int) -> dict[str, Any]:
        operation = self.repository.get_carousel_operation(int(operation_id))
        if operation is None or int(operation.get("scheme_id") or 0) != int(item_id):
            raise GenerationNotFoundError("轮播操作不存在")
        scheme = self.repository.get_display_scheme(int(item_id))
        if scheme is None:
            raise GenerationNotFoundError("展示方案不存在")
        return {
            "operation": self.public_mapper.carousel_operation(operation),
            "scheme": self.public_mapper.display_scheme(scheme),
        }

    def adopt_visual(self, project_id: int, item_id: int) -> dict[str, Any]:
        reference_id, source = self.repository.visual_adoption_source(project_id, item_id)
        snapshot = self.public_mapper.result_item(source, recommendation_kind="visual")
        self.repository.save_adoption(project_id, "visual", reference_id, snapshot)
        return snapshot

    def adopt_narrative(
        self,
        project_id: int,
        generation_id: int,
        item_index: int,
    ) -> dict[str, Any]:
        reference_id, source = self.repository.narrative_adoption_source(
            project_id,
            generation_id,
            item_index,
        )
        snapshot = self.public_mapper.result_item(source, recommendation_kind="narrative")
        self.repository.save_adoption(project_id, "narrative", reference_id, snapshot)
        return snapshot


_DEFAULT_MODEL_CLIENT = object()


def create_application(
    *,
    database_path: Path = DATABASE_PATH,
    images_dir: Path = IMAGES_DIR,
    uploads_dir: Path = UPLOADS_DIR,
    model_client: ModelClient | None | object = _DEFAULT_MODEL_CLIENT,
    image_runner: Any | None = None,
    image_client: GptWebImageClient | None = None,
    clock: Callable[[], str] | None = None,
    environment: MutableMapping[str, str] | None = None,
    prompt_registry: PromptRegistry | None = None,
    ai_v2_text_model: TextModelPort | None = None,
    ai_v2_image_model: ImageModelPort | None = None,
) -> StudioApplication:
    """Build the application graph, allowing deterministic adapters in tests."""

    source = environment if environment is not None else os.environ
    StudioApplication._ensure_default_ai_environment(source)
    prompt_registry = prompt_registry or PromptRegistry.load(PROMPT_REGISTRY_PATH)
    public_mapper = PublicResultMapper()
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
    if image_runner is None:
        client = image_client or GptWebImageClient(
            gateway_base_from_environment(source),
            source.get("WEB_ERP_AI_CONTROL_TOKEN", ""),
        )
        image_runner = ImageJobRunner(repository, images_dir, client)
    resolved_model_client = (
        StudioApplication._load_model_client(source)
        if model_client is _DEFAULT_MODEL_CLIENT
        else model_client
    )
    generation_service = CreativeGenerationService(
        repository,
        model_client=resolved_model_client,
        image_runner=image_runner,
        environment=source,
        prompt_registry=prompt_registry,
        reference_asset_port=FileReferenceAssetStore(repository, uploads_dir),
        observability=StructuredObservability(),
    )
    generation_service.recover_carousel_operations()

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
        text_model = ai_v2_text_model if ai_v2_text_model is not None else TextGatewayAdapter(
            transport,
            base_url=gateway_url,
            model=model,
        )
        image_model = ai_v2_image_model if ai_v2_image_model is not None else ImageGatewayAdapter(
            transport,
            base_url=gateway_url,
        )
        return AiV2Application(
            SqliteAiV2Store(database_path),
            text_model=text_model,
            image_model=image_model,
            project_provider=repository.get_project,
        )

    return StudioApplication(
        repository,
        auth,
        image_runner,
        generation_service,
        public_mapper=public_mapper,
        uploads_dir=uploads_dir,
        prompt_registry=prompt_registry,
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

        project_match = re.fullmatch(r"/api/v2/projects/(\d+)/(?:generate|history)", path)
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
                "projects": [self.application.public_mapper.project_summary(project) for project in projects],
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
                    "project": self.application.public_mapper.project(project),
                })
            return
        history_match = re.fullmatch(r"/api/projects/(\d+)/history", path)
        if history_match:
            context = self._context()
            self._require_project_access(int(history_match.group(1)), context)
            self._json(self.application.history(int(history_match.group(1))))
            return
        frame_status_match = re.fullmatch(r"/api/visual-items/(\d+)/frames/status", path)
        if frame_status_match:
            scheme_id = int(frame_status_match.group(1))
            owner = self.application.repository.get_visual_item_owner_id(scheme_id)
            context = self._context()
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            scheme = self.application.repository.get_display_scheme(scheme_id)
            if scheme is None:
                self._json({"success": False, "error": "展示方案不存在"}, HTTPStatus.NOT_FOUND)
            else:
                payload = {
                    "success": True,
                    "scheme": self.application.public_mapper.display_scheme(scheme),
                }
                operation = self.application.repository.latest_carousel_operation(scheme_id)
                if operation is not None:
                    payload["operation"] = self.application.public_mapper.carousel_operation(operation)
                self._json(payload)
            return
        operation_match = re.fullmatch(r"/api/visual-items/(\d+)/operation/(\d+)", path)
        if operation_match:
            scheme_id, operation_id = int(operation_match.group(1)), int(operation_match.group(2))
            owner = self.application.repository.get_visual_item_owner_id(scheme_id)
            context = self._context()
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            result = self.application.carousel_operation_status(scheme_id, operation_id)
            self._json({"success": True, **result})
            return
        status_match = re.fullmatch(r"/api/visual-items/(\d+)/status", path)
        if status_match:
            context = self._context()
            owner = self.application.repository.get_visual_item_owner_id(int(status_match.group(1)))
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            item = self.application.repository.visual_item(int(status_match.group(1)))
            if item is None:
                self._json({"success": False, "error": "图片任务不存在"}, HTTPStatus.NOT_FOUND)
            else:
                self._json({
                    "success": True,
                    "item": self.application.public_mapper.visual_status(item),
                })
            return
        image_match = re.fullmatch(r"/api/visual-items/(\d+)/image", path)
        if image_match:
            context = self._context()
            owner = self.application.repository.get_visual_item_owner_id(int(image_match.group(1)))
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            image_path = self.application.repository.image_path_for_item(int(image_match.group(1)))
            if image_path is None or not image_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._file(image_path, cache="no-store")
            return
        frame_image_match = re.fullmatch(r"/api/visual-items/(\d+)/frames/(\d+)/image", path)
        if frame_image_match:
            scheme_id = int(frame_image_match.group(1))
            frame_index = int(frame_image_match.group(2))
            owner = self.application.repository.get_visual_item_owner_id(scheme_id)
            context = self._context()
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            image_path = self.application.repository.image_path_for_frame(scheme_id, frame_index)
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
                "project": self.application.public_mapper.project(project),
            }, HTTPStatus.CREATED)
            return
        generate_match = re.fullmatch(r"/api/projects/(\d+)/generate", path)
        if generate_match:
            self._require_project_access(int(generate_match.group(1)), self._context())
            self._json(self.application.generate(int(generate_match.group(1))))
            return
        scheme_match = re.fullmatch(r"/api/visual-items/(\d+)/(select|continue)", path)
        if scheme_match:
            item_id, action = int(scheme_match.group(1)), scheme_match.group(2)
            owner = self.application.repository.get_visual_item_owner_id(item_id)
            context = self._context()
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            result = self.application.select_visual_scheme(item_id) if action == "select" else self.application.continue_visual_scheme(item_id)
            self._json({"success": True, **result}, HTTPStatus.ACCEPTED if action == "continue" else HTTPStatus.OK)
            return
        adopt_match = re.fullmatch(r"/api/projects/(\d+)/adopt", path)
        if adopt_match:
            project_id = int(adopt_match.group(1))
            self._require_project_access(project_id, self._context())
            data = self._read_json()
            if data.get("recommendation_kind") == "narrative":
                snapshot = self.application.adopt_narrative(
                    project_id, int(data.get("generation_id") or 0), int(data.get("item_index") or 0)
                )
            else:
                snapshot = self.application.adopt_visual(project_id, int(data.get("item_id") or 0))
            self._json({
                "success": True,
                "snapshot": snapshot,
            })
            return
        retry_match = re.fullmatch(r"/api/visual-items/(\d+)/retry", path)
        if retry_match:
            item_id = int(retry_match.group(1))
            owner = self.application.repository.get_visual_item_owner_id(item_id)
            context = self._context()
            if context.user.get("role") != "admin" and owner != context.user.get("id"):
                self._json({"success": False, "error": "无权访问该项目"}, HTTPStatus.FORBIDDEN)
                return
            if not self.application.repository.retry_visual_item(item_id):
                raise StudioDataError("只有失败的图片可以重新生成")
            self.application.image_runner.retry(item_id)
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
            "project": self.application.public_mapper.project(project),
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
        if isinstance(exc, GenerationInputError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        if isinstance(exc, GenerationNotFoundError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.NOT_FOUND)
            return
        if isinstance(exc, GenerationConflictError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.CONFLICT)
            return
        if isinstance(exc, GenerationQueueTimeoutError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if isinstance(exc, StudioDataError):
            self._json({"success": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if isinstance(exc, AiCreativeConfigurationError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if isinstance(exc, AiCreativeQueueTimeoutError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if isinstance(exc, AiCreativeRequestError):
            self._json(StudioHandler._generation_error_payload(exc), HTTPStatus.BAD_GATEWAY)
            return
        traceback.print_exc()
        self._json({"success": False, "error": "服务处理失败，请查看启动窗口日志"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    @staticmethod
    def _generation_error_payload(exc: Exception) -> dict[str, Any]:
        details = error_details(exc)
        return {
            "success": False,
            "error": str(exc),
            **details.public_fields(),
        }


class _ResponseHandled(Exception):
    """Internal control flow after an error response has been written."""


def run() -> None:
    host = str(os.environ.get("CREATIVE_STUDIO_HOST") or "127.0.0.1")
    port = int(os.environ.get("CREATIVE_STUDIO_PORT") or 8775)
    application = create_application()
    server = ThreadingHTTPServer((host, port), StudioHandler)
    server.application = application  # type: ignore[attr-defined]
    application.image_runner.start()
    print(f"AI创意工作台：http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        application.generation_service.stop()
        application.image_runner.stop()
        if application._ai_v2_application is not None:
            application._ai_v2_application.store.close()
        server.server_close()


if __name__ == "__main__":
    run()
