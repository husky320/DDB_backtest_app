from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DDBConfigRequest(BaseModel):
    host: str
    port: int
    username: str
    password: str
    candidate_ports: list[int] = Field(default_factory=lambda: [8030, 8031, 8032, 8033])
    preferred_data_node: str = ""


class LLMConfigRequest(BaseModel):
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    enabled: bool = True


class BacktestRunRequest(BaseModel):
    template_id: str
    user_config: dict[str, Any] = Field(default_factory=dict)
    ai_patch: dict[str, Any] | None = None
    auto_fallback_benchmark: bool = True


class AIRecommendRequest(BaseModel):
    mode: str = "config_patch"
    template_id: str | None = None
    selected_ranges: list[str] = Field(default_factory=list)
    selected_fundamental_factors: list[str] = Field(default_factory=list)
    selected_technical_factors: list[str] = Field(default_factory=list)
    goal: str = "稳健收益"
    current_config: dict[str, Any] = Field(default_factory=dict)
    backtest_tasks: list[dict[str, Any]] = Field(default_factory=list)


class AIChatRequest(BaseModel):
    message: str
    current_config: dict[str, Any] = Field(default_factory=dict)


class SemanticAnalyzeRequest(BaseModel):
    strategy_text: str
