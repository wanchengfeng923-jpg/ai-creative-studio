from __future__ import annotations

from http import HTTPStatus
import unittest

from creative_studio.ai_creative import (
    AiCreativeConfigurationError,
    AiCreativeQueueTimeoutError,
    AiCreativeRequestError,
)
from creative_studio.app import StudioHandler
from creative_studio.generation_models import (
    GenerationConflictError,
    GenerationInputError,
    GenerationNotFoundError,
    GenerationQueueTimeoutError,
)
from creative_studio.repository import StudioDataError


class DummyHandler:
    def __init__(self) -> None:
        self.responses: list[tuple[dict[str, object], HTTPStatus]] = []

    def _json(self, payload, status=HTTPStatus.OK):
        self.responses.append((payload, HTTPStatus(status)))


class AppApiTests(unittest.TestCase):
    def test_generation_errors_map_to_expected_http_statuses(self) -> None:
        cases = [
            (GenerationInputError("输入不合法"), HTTPStatus.UNPROCESSABLE_ENTITY),
            (GenerationNotFoundError("项目不存在"), HTTPStatus.NOT_FOUND),
            (GenerationConflictError("状态冲突"), HTTPStatus.CONFLICT),
            (GenerationQueueTimeoutError("队列超时"), HTTPStatus.SERVICE_UNAVAILABLE),
            (AiCreativeQueueTimeoutError("AI排队超时"), HTTPStatus.SERVICE_UNAVAILABLE),
            (AiCreativeConfigurationError("配置错误"), HTTPStatus.INTERNAL_SERVER_ERROR),
            (AiCreativeRequestError("上游失败"), HTTPStatus.BAD_GATEWAY),
        ]
        for exc, expected_status in cases:
            handler = DummyHandler()
            StudioHandler._error(handler, exc)
            self.assertEqual(handler.responses, [({"success": False, "error": str(exc)}, expected_status)])

    def test_generic_studio_data_error_still_maps_to_bad_request(self) -> None:
        handler = DummyHandler()
        StudioHandler._error(handler, StudioDataError("普通数据错误"))
        self.assertEqual(handler.responses, [({"success": False, "error": "普通数据错误"}, HTTPStatus.BAD_REQUEST)])


if __name__ == "__main__":
    unittest.main()
