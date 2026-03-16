from __future__ import annotations

from app.services.semantic_strategy_service import SemanticStrategyService


class _DummyLLMConfigManager:
    def get(self):
        raise AssertionError("LLM config should not be accessed for empty strategy text")


class _DummyRegistry:
    pass


def test_analyze_empty_text_returns_unsupported_instead_of_error():
    service = SemanticStrategyService(_DummyLLMConfigManager(), _DummyRegistry())
    result = service.analyze("   ")

    assert result["supported"] is False
    assert result["framework_supported"] is False
    assert "策略描述为空" in result["message"]
