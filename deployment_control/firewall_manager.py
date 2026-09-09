"""仅管理 AI 创意工作台公网 Web 的固定 Windows 防火墙规则。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


FIREWALL_RULE_NAME = "AI Creative Studio Web 8775"
FIREWALL_PORT = 8775
FIREWALL_PROTOCOL = "TCP"
FIREWALL_DIRECTION = "Inbound"
FIREWALL_ACTION = "Allow"


@dataclass(frozen=True)
class FirewallRule:
    name: str
    local_port: int
    protocol: str
    direction: str
    action: str
    enabled: bool


class FirewallRunner(Protocol):
    def inspect_rule(self, name: str) -> Iterable[FirewallRule]:
        ...

    def create_rule(
        self,
        name: str,
        local_port: int,
        protocol: str,
        direction: str,
        action: str,
    ) -> None:
        ...

    def enable_rule(self, name: str) -> None:
        ...

    def disable_rule(self, name: str) -> None:
        ...

    def remove_rule(self, name: str) -> None:
        ...


class FirewallManager:
    """固定规则的检查、创建、启用、禁用和删除接口。"""

    def __init__(self, runner: FirewallRunner) -> None:
        self.runner = runner

    def inspect(self) -> FirewallRule | None:
        rules = list(self.runner.inspect_rule(FIREWALL_RULE_NAME))
        if len(rules) > 1:
            raise ValueError("固定防火墙规则存在重复项")
        if not rules:
            return None
        rule = rules[0]
        self._validate(rule)
        return rule

    def enable(self) -> None:
        rule = self.inspect()
        if rule is None:
            self.runner.create_rule(
                FIREWALL_RULE_NAME,
                FIREWALL_PORT,
                FIREWALL_PROTOCOL,
                FIREWALL_DIRECTION,
                FIREWALL_ACTION,
            )
        self.runner.enable_rule(FIREWALL_RULE_NAME)

    def disable(self) -> None:
        rule = self.inspect()
        if rule is not None and rule.enabled:
            self.runner.disable_rule(FIREWALL_RULE_NAME)

    def remove(self) -> None:
        rule = self.inspect()
        if rule is not None:
            self.runner.remove_rule(FIREWALL_RULE_NAME)

    @staticmethod
    def _validate(rule: FirewallRule) -> None:
        expected = (
            FIREWALL_RULE_NAME,
            FIREWALL_PORT,
            FIREWALL_PROTOCOL,
            FIREWALL_DIRECTION,
            FIREWALL_ACTION,
        )
        actual = (
            rule.name,
            rule.local_port,
            rule.protocol,
            rule.direction,
            rule.action,
        )
        if actual != expected:
            raise ValueError("固定防火墙规则字段不符合项目边界")
