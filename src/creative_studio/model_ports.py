"""可替换的文字/图片模型 Port 及确定性测试适配器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .model_client import ModelRequest, ModelResponse
from .provider_capabilities import ProviderCapabilities


class TextModelPort(Protocol):
    capabilities: ProviderCapabilities

    def generate(self, request: ModelRequest) -> ModelResponse:
        ...

    def complete(self, request: ModelRequest) -> ModelResponse:
        ...


@dataclass(frozen=True)
class ImageModelRequest:
    prompt: str
    aspect_ratio: str = "16:9"
    reference_images: tuple[bytes, ...] = ()
    reference_mimes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImageJobRef:
    job_id: str


class ImageModelPort(Protocol):
    capabilities: ProviderCapabilities

    def submit(self, request: ImageModelRequest, *, request_id: str = "") -> ImageJobRef:
        ...


class DeterministicTextModel:
    """不读取环境、不联网的可编程文字 fake。"""

    capabilities = ProviderCapabilities(
        structured_output_enforced=False,
        token_limit_enforced=False,
        conversation_resume=True,
        multimodal_input=False,
    )

    def __init__(self, responses: Sequence[ModelResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("deterministic text fake exhausted")
        return self.responses.pop(0)

    def complete(self, request: ModelRequest) -> ModelResponse:
        return self.generate(request)


class DeterministicImageModel:
    """不读取环境、不访问图片网关的确定性图片 fake。"""

    capabilities = ProviderCapabilities(
        structured_output_enforced=False,
        token_limit_enforced=False,
        conversation_resume=False,
        multimodal_input=True,
    )

    def __init__(self) -> None:
        self.requests: list[ImageModelRequest] = []
        self.jobs: list[ImageJobRef] = []

    def submit(self, request: ImageModelRequest, *, request_id: str = "") -> ImageJobRef:
        self.requests.append(request)
        ref = ImageJobRef(request_id or f"fake-image-{len(self.jobs) + 1}")
        self.jobs.append(ref)
        return ref


__all__ = [
    "DeterministicImageModel", "DeterministicTextModel", "ImageJobRef", "ImageModelPort",
    "ImageModelRequest", "ProviderCapabilities", "TextModelPort",
]
