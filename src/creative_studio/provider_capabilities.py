"""外部模型供应商能力声明。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    structured_output_enforced: bool = False
    token_limit_enforced: bool = False
    conversation_resume: bool = False
    multimodal_input: bool = False
