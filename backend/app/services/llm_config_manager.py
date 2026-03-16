from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.storage import read_json, write_json


@dataclass
class LLMConfig:
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    enabled: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LLMConfig":
        return cls(
            provider=str(payload.get("provider", "deepseek")),
            base_url=str(payload.get("base_url", "https://api.deepseek.com/v1")),
            model=str(payload.get("model", "deepseek-chat")),
            api_key=str(payload.get("api_key", "")),
            temperature=float(payload.get("temperature", 0.2)),
            max_tokens=int(payload.get("max_tokens", 1200)),
            enabled=bool(payload.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enabled": self.enabled,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": "",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
        }


class LLMConfigManager:
    def __init__(self, config_file: Path) -> None:
        self._config_file = config_file
        self._config = self._load()

    def _load(self) -> LLMConfig:
        payload = read_json(self._config_file, {})
        return LLMConfig.from_dict(payload)

    def get(self) -> LLMConfig:
        return self._config

    def get_public(self) -> dict[str, Any]:
        return self._config.to_public_dict()

    def update(self, payload: dict[str, Any]) -> LLMConfig:
        merged = dict(payload)
        if not str(merged.get("api_key", "")).strip():
            merged["api_key"] = self._config.api_key
        self._config = LLMConfig.from_dict(merged)
        write_json(self._config_file, self._config.to_dict())
        return self._config
