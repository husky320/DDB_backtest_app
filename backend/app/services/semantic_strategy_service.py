from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.services.llm_config_manager import LLMConfigManager
from app.services.script_registry import DolphinDBScriptRegistry


class SemanticStrategyService:
    def __init__(self, llm_config_manager: LLMConfigManager, registry: DolphinDBScriptRegistry) -> None:
        self._llm_config_manager = llm_config_manager
        self._registry = registry

    def analyze(self, strategy_text: str) -> dict[str, Any]:
        text = strategy_text.strip()
        if not text:
            return self._unsupported("平台暂不支持：用户策略描述为空，无法进行任何分析或判断。")

        llm_cfg = self._llm_config_manager.get()
        if not llm_cfg.enabled:
            return self._unsupported("平台暂不支持：LLM 能力已关闭。")
        if not llm_cfg.api_key:
            return self._unsupported("平台暂不支持：未配置 LLM API Key。")

        factor_meta = self._registry.get_factor_meta()
        templates = self._registry.list_templates()
        capabilities = {
            "templates": [
                {"template_id": x["template_id"], "label": x["label"], "strategy_type": x["strategy_type"]}
                for x in templates
            ],
            "fundamental_factors": factor_meta.get("fundamental_factors", []),
            "technical_factors": factor_meta.get("technical_factors", []),
            "timing_signal_map": factor_meta.get("timing_signal_map", {}),
            "supported_technical_rules": [
                "ma_above",
                "ma_below",
                "ma_bull_arrangement",
                "macd_golden",
                "macd_dead",
                "rsi_threshold",
                "kdj_golden",
                "kdj_dead",
                "boll_break_upper",
                "boll_break_lower",
                "bbi_break",
            ],
        }

        prompt = self._build_prompt(text, capabilities)
        try:
            raw = self._chat(prompt)
            payload = self._extract_json_object(raw)
        except Exception as exc:
            return self._unsupported(f"平台暂不支持：语义解析失败（{exc}）。")

        framework_supported = bool(payload.get("framework_supported", False))
        required_new_factors = payload.get("required_new_factors", [])
        if not isinstance(required_new_factors, list):
            required_new_factors = []

        normalized_factors: list[dict[str, Any]] = []
        has_unwritable = False
        for item in required_new_factors:
            if not isinstance(item, dict):
                continue
            writable = bool(item.get("writable", False))
            if not writable:
                has_unwritable = True
            normalized_factors.append(
                {
                    "name": str(item.get("name", "")),
                    "description": str(item.get("description", "")),
                    "writable": writable,
                    "reason": str(item.get("reason", "")),
                }
            )

        recommended_existing = payload.get("recommended_existing_factors", [])
        if not isinstance(recommended_existing, list):
            recommended_existing = []
        recommended_existing = [str(x) for x in recommended_existing if str(x).strip()]

        if not framework_supported:
            reason = str(payload.get("framework_reason", "")).strip() or "当前描述超出回测框架能力范围。"
            return self._unsupported(f"平台暂不支持：{reason}", normalized_factors, recommended_existing)

        if has_unwritable:
            return self._unsupported(
                "平台暂不支持：存在当前无法实现的新因子，请调整策略描述。",
                normalized_factors,
                recommended_existing,
            )

        reply_text = str(payload.get("response_text", "")).strip() or "策略可在当前框架执行。"
        return {
            "supported": True,
            "framework_supported": True,
            "message": reply_text,
            "required_new_factors": normalized_factors,
            "recommended_existing_factors": recommended_existing,
        }

    def _unsupported(
        self,
        message: str,
        required_new_factors: list[dict[str, Any]] | None = None,
        recommended_existing: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "supported": False,
            "framework_supported": False,
            "message": message,
            "required_new_factors": required_new_factors or [],
            "recommended_existing_factors": recommended_existing or [],
        }

    def _build_prompt(self, strategy_text: str, capabilities: dict[str, Any]) -> str:
        return (
            "你是量化回测产品的策略解释器，请严格输出 JSON 对象，不要输出 Markdown。\n"
            "任务：根据用户策略描述，判断当前平台是否支持。\n"
            "必须输出字段：\n"
            "{\n"
            '  "framework_supported": boolean,\n'
            '  "framework_reason": string,\n'
            '  "required_new_factors": [\n'
            '    {"name": string, "description": string, "writable": boolean, "reason": string}\n'
            "  ],\n"
            '  "recommended_existing_factors": [string],\n'
            '  "response_text": string\n'
            "}\n"
            "解释规则：\n"
            "1. framework_supported=false 时，response_text 必须是“平台暂不支持...”开头。\n"
            "2. required_new_factors 用于识别需要新写因子。\n"
            "3. writable=false 表示该新因子当前无法实现。\n"
            "4. recommended_existing_factors 仅返回平台已有可用因子标签。\n"
            f"平台能力：{json.dumps(capabilities, ensure_ascii=False)}\n"
            f"用户策略描述：{strategy_text}\n"
        )

    def _chat(self, prompt: str) -> str:
        cfg = self._llm_config_manager.get()
        url = cfg.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": cfg.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "messages": [
                {"role": "system", "content": "你是严格返回 JSON 的量化策略分析助手。"},
                {"role": "user", "content": prompt},
            ],
        }
        # Avoid inheriting system proxy env vars (e.g. SOCKS) that can break
        # local deployments without optional socks dependencies.
        with httpx.Client(timeout=80, trust_env=False) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            raise ValueError("empty llm response")

        candidates: list[str] = [raw]

        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
        if fenced:
            candidates.append(fenced.group(1).strip())

        obj_span = self._find_balanced_json_object(raw)
        if obj_span:
            candidates.append(obj_span)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        raise ValueError("invalid llm json response")

    def _find_balanced_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None
