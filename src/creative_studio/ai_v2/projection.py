"""AI v2 浏览器公开 DTO：从空对象按 schema 白名单重建。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_IMAGE_STATUSES = frozenset({"pending", "generating", "success", "failed"})
_SAFE_ERROR_CODE = re.compile(r"^[a-z0-9_.-]{1,80}$")
_TEXT_FIELDS = ("story", "text", "title", "core_idea", "ad_copy", "image_description", "description")


def _copy_text(source: Mapping[str, Any], key: str, target: dict[str, Any]) -> None:
    value = source.get(key)
    if isinstance(value, str):
        target[key] = value


def public_image_state(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """将内部 attempt 投影为不含供应商事实的安全状态。"""

    status = attempt.get("status")
    if status not in _IMAGE_STATUSES:
        raise ValueError("invalid public image status")
    result: dict[str, Any] = {"status": status}
    for key in ("attempt_id", "attempt_no"):
        value = attempt.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            result[key] = value
    retryable = attempt.get("retryable")
    if isinstance(retryable, bool):
        result["retryable"] = retryable
    error_code = attempt.get("error_code")
    if isinstance(error_code, str) and _SAFE_ERROR_CODE.fullmatch(error_code):
        result["error_code"] = error_code
    image_url = attempt.get("image_url")
    if isinstance(image_url, str) and image_url.startswith("/api/v2/"):
        result["image_url"] = image_url
    operation_id = attempt.get("operation_id")
    if isinstance(operation_id, (int, str)) and not isinstance(operation_id, bool):
        result["operation_id"] = operation_id
    return result


def _public_narrative_item(item: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    _copy_text(item, "story", result)
    hooks: list[dict[str, Any]] = []
    raw_hooks = item.get("hooks")
    if isinstance(raw_hooks, Sequence) and not isinstance(raw_hooks, (str, bytes, bytearray)):
        for raw_hook in raw_hooks:
            if not isinstance(raw_hook, Mapping):
                continue
            hook: dict[str, Any] = {}
            _copy_text(raw_hook, "text", hook)
            scenes = raw_hook.get("scenes")
            if isinstance(scenes, Sequence) and not isinstance(scenes, (str, bytes, bytearray)):
                hook["scenes"] = [scene for scene in scenes if isinstance(scene, str)]
            hooks.append(hook)
    if hooks:
        result["hooks"] = hooks
    return result


def public_scheme(scheme: Mapping[str, Any]) -> dict[str, Any]:
    """按用例白名单构造单个公开方案，不读取内部 execution。"""

    canonical = scheme.get("canonical")
    source = canonical if isinstance(canonical, Mapping) else scheme
    use_case = str(scheme.get("use_case") or source.get("use_case") or "").strip().lower()
    result: dict[str, Any] = {}
    for key in ("scheme_id", "item_index", "scheme_index"):
        value = scheme.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            result[key] = value

    if use_case == "narrative":
        return _public_narrative_item(source)

    for key in ("title", "core_idea", "ad_copy", "image_description"):
        _copy_text(source, key, result)

    if use_case == "carousel":
        frames: list[dict[str, Any]] = []
        raw_frames = source.get("frames")
        if isinstance(raw_frames, Sequence) and not isinstance(raw_frames, (str, bytes, bytearray)):
            for raw_frame in raw_frames:
                if not isinstance(raw_frame, Mapping):
                    continue
                frame: dict[str, Any] = {}
                index = raw_frame.get("index")
                if isinstance(index, int) and not isinstance(index, bool):
                    frame["index"] = index
                _copy_text(raw_frame, "description", frame)
                frame_state = raw_frame.get("image_state")
                if isinstance(frame_state, Mapping):
                    frame["image_state"] = public_image_state(frame_state)
                frames.append(frame)
        if frames:
            result["frames"] = frames
    image_state = scheme.get("image_state")
    if isinstance(image_state, Mapping):
        result["image_state"] = public_image_state(image_state)
    return result


def public_run(run: Mapping[str, Any]) -> dict[str, Any]:
    """构造公开运行结果，统一过滤内部 canonical 和会话信息。"""

    result: dict[str, Any] = {}
    for key in ("run_id", "project_id", "batch_index"):
        value = run.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            result[key] = value
    use_case = str(run.get("use_case") or "").strip().lower()
    if use_case in {"narrative", "static", "carousel"}:
        result["use_case"] = use_case
    status = run.get("status")
    if isinstance(status, str) and status in {"pending", "success", "failed", "accepted", "text_succeeded", "partial", "completed"}:
        result["status"] = status

    canonical = run.get("canonical")
    source = canonical if isinstance(canonical, Mapping) else run
    schema_version = source.get("schema_version")
    if isinstance(schema_version, str) and schema_version in {"narrative-text-v1", "static-text-v1", "carousel-text-v1"}:
        result["schema_version"] = schema_version

    raw_schemes = run.get("schemes")
    if isinstance(raw_schemes, Sequence) and not isinstance(raw_schemes, (str, bytes, bytearray)):
        items = [public_scheme({**scheme, "use_case": use_case}) for scheme in raw_schemes if isinstance(scheme, Mapping)]
    else:
        raw_items = source.get("items")
        items = []
        if isinstance(raw_items, Sequence) and not isinstance(raw_items, (str, bytes, bytearray)):
            for index, item in enumerate(raw_items, start=1):
                if not isinstance(item, Mapping):
                    continue
                if use_case == "narrative":
                    items.append(_public_narrative_item(item))
                else:
                    items.append(public_scheme({**item, "use_case": use_case, "item_index": index}))
    result["items"] = items
    return result


__all__ = ["public_image_state", "public_run", "public_scheme"]

