from __future__ import annotations

import re
from typing import Any


class AISkillOrchestrator:
    _allowed_actions = [
        "改参数",
        "改因子",
        "改基准",
        "改区间",
        "切模板",
        "触发回测",
    ]

    _out_of_scope_keywords = [
        "实盘下单",
        "自动交易",
        "新闻预测",
        "舆情",
        "机器学习训练",
        "超出回测",
    ]
    _out_of_scope_patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"实盘.*下单|下单.*实盘", re.IGNORECASE), "实盘下单"),
        (re.compile(r"auto\s*trade|live\s*trade", re.IGNORECASE), "自动交易"),
        (re.compile(r"自动.*交易|自动.*下单|程序化.*下单"), "自动交易"),
        (re.compile(r"新闻.*预测|舆情"), "新闻预测"),
        (re.compile(r"机器学习.*训练|深度学习.*训练|模型训练"), "机器学习训练"),
    ]
    _benchmark_map = {
        "000300.SH": "沪深300",
        "000002.SZ": "万科A",
    }

    def recommend(self, payload: dict[str, Any]) -> dict[str, Any]:
        if str(payload.get("mode", "config_patch")).strip() == "strategy_ideas":
            return self._recommend_strategy_ideas(payload)
        return self._recommend_config_patch(payload)

    def _recommend_config_patch(self, payload: dict[str, Any]) -> dict[str, Any]:
        goal = str(payload.get("goal", "稳健收益"))
        selected_fundamental = payload.get("selected_fundamental_factors", [])
        selected_technical = payload.get("selected_technical_factors", [])
        current = dict(payload.get("current_config", {}))

        patch: dict[str, Any] = {}
        hints: list[str] = []
        skills: list[str] = []

        if "稳健" in goal:
            patch.update(
                {
                    "holdingPeriod": 45,
                    "perStockPercent": 0.08,
                    "dailyBuyCountLimit": max(int(current.get("dailyBuyCountLimit", 2)), 2),
                }
            )
            hints.append("稳健目标建议提高持仓稳定性并降低单票仓位。")
            skills.append("仓位风控技能")
        elif "进攻" in goal or "高收益" in goal:
            patch.update({"holdingPeriod": 20, "perStockPercent": 0.12, "dailyBuyCountLimit": 4})
            hints.append("进攻目标建议缩短持仓并增加换手。")
            skills.append("买卖择时技能")

        buy_factors = list(current.get("buyFactors", []))
        buy_condition_parts: list[str] = []

        if "市盈率" in selected_fundamental and "pe" not in buy_factors:
            buy_factors.append("pe")
            buy_condition_parts.append("pe < 80")
            skills.append("基本面因子技能")
        if "总市值" in selected_fundamental and "total_mv" not in buy_factors:
            buy_factors.append("total_mv")
            buy_condition_parts.append("total_mv < 12000000")
            skills.append("基本面因子技能")
        if "MA" in selected_technical:
            if "close" not in buy_factors:
                buy_factors.append("close")
            if "ma5" not in buy_factors:
                buy_factors.append("ma5")
            buy_condition_parts.append("close > ma5")
            skills.append("技术面因子技能")
        if "MACD" in selected_technical:
            sell_factors = list(current.get("sellFactors", []))
            if "macdDeadCross" not in sell_factors:
                sell_factors.append("macdDeadCross")
            patch["sellFactors"] = sell_factors
            patch["sellFactorConditions"] = "macdDeadCross == 1"
            hints.append("保留 MACD 死叉作为退出条件，可以减少趋势反转时的回撤。")

        if buy_factors:
            patch["buyFactors"] = buy_factors
        if buy_condition_parts:
            existing = str(current.get("buyFactorConditions", "")).strip()
            if existing:
                patch["buyFactorConditions"] = f"({existing}) and " + " and ".join(buy_condition_parts)
            else:
                patch["buyFactorConditions"] = " and ".join(buy_condition_parts)

        if not skills:
            skills = ["规则推荐技能"]

        return {
            "skills": sorted(set(skills)),
            "config_patch": patch,
            "hints": hints or ["可以先设置目标（稳健/进攻），再让我自动回填参数。"],
        }

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _to_rule_sets(self, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        custom = config.get("factorCustomization")
        empty = {"logic": "and", "fundamentals": [], "technicals": []}
        if not isinstance(custom, dict):
            return empty, empty
        if "buy" in custom or "sell" in custom:
            buy = custom.get("buy") if isinstance(custom.get("buy"), dict) else empty
            sell = custom.get("sell") if isinstance(custom.get("sell"), dict) else empty
            return buy, sell
        return custom, empty

    def _format_number(self, value: Any) -> str:
        try:
            number = float(value)
        except Exception:
            return str(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.4f}".rstrip("0").rstrip(".")

    def _rule_to_phrase(self, rule: dict[str, Any], side: str) -> str:
        field = str(rule.get("field", "")).strip()
        op = str(rule.get("op", "")).strip()
        value = self._format_number(rule.get("value"))
        suffix = "买入" if side == "buy" else "卖出"
        field_label = {
            "total_mv": "总市值",
            "pe": "市盈率",
            "amount": "成交额",
        }.get(field, field)
        return f"{field_label}{op}{value}{suffix}"

    def _technical_to_phrase(self, rule: dict[str, Any], side: str) -> str:
        period = int(rule.get("period", 5) or 5)
        rtype = str(rule.get("type", "")).strip()
        mapping = {
            "ma_above": f"股价站上{period}日线买入",
            "ma_below": f"股价跌破{period}日线卖出",
            "ma_bull_arrangement": "均线多头排列买入",
            "macd_golden": "MACD金叉买入",
            "macd_dead": "MACD死叉卖出",
            "rsi_threshold": f"RSI{rule.get('op', '<')}{self._format_number(rule.get('value'))}{'买入' if side == 'buy' else '卖出'}",
            "kdj_golden": "KDJ金叉买入",
            "kdj_dead": "KDJ死叉卖出",
            "boll_break_upper": "股价突破布林上轨买入",
            "boll_break_lower": "股价跌破布林下轨卖出",
            "bbi_break": "股价下穿BBI卖出",
        }
        return mapping.get(rtype, str(rule.get("label", "")).strip())

    def _parse_condition_text(self, text: str, side: str) -> list[str]:
        clauses: list[str] = []
        mapping: list[tuple[re.Pattern[str], str]] = [
            (re.compile(r"total_mv\s*(<=|>=|<|>|==|!=)\s*(\d+(?:\.\d+)?)"), "总市值{op}{value}"),
            (re.compile(r"pe\s*(<=|>=|<|>|==|!=)\s*(\d+(?:\.\d+)?)"), "市盈率{op}{value}"),
            (re.compile(r"amount\s*(<=|>=|<|>|==|!=)\s*(\d+(?:\.\d+)?)"), "成交额{op}{value}"),
            (re.compile(r"close\s*>\s*ma(\d+)"), "股价站上{value}日线"),
            (re.compile(r"close\s*<\s*ma(\d+)"), "股价跌破{value}日线"),
            (re.compile(r"macdDeadCross\s*==\s*1"), "MACD死叉"),
            (re.compile(r"macdDeadCross\s*==\s*0"), "MACD金叉"),
            (re.compile(r"kdjDeadCross\s*==\s*1"), "KDJ死叉"),
            (re.compile(r"kdjDeadCross\s*==\s*0"), "KDJ金叉"),
            (re.compile(r"breakBBI\s*==\s*1"), "股价下穿BBI"),
            (re.compile(r"close\s*>\s*bollBreakUpper"), "股价突破布林上轨"),
            (re.compile(r"close\s*<\s*bollBreakLower"), "股价跌破布林下轨"),
            (re.compile(r"rsi12\s*(<=|>=|<|>|==|!=)\s*(\d+(?:\.\d+)?)"), "RSI{op}{value}"),
        ]
        for pattern, template in mapping:
            match = pattern.search(text)
            if not match:
                continue
            if "{op}" in template:
                phrase = template.format(op=match.group(1), value=match.group(2))
            else:
                phrase = template.format(value=match.group(1))
            clauses.append(f"{phrase}{'买入' if side == 'buy' else '卖出'}")
        return clauses

    def _config_to_semantic_text(self, config: dict[str, Any]) -> str:
        buy_rules, sell_rules = self._to_rule_sets(config)
        parts: list[str] = []

        for rule in buy_rules.get("fundamentals", []):
            if isinstance(rule, dict) and bool(rule.get("enabled", True)):
                parts.append(self._rule_to_phrase(rule, "buy"))
        for rule in buy_rules.get("technicals", []):
            if isinstance(rule, dict) and bool(rule.get("enabled", True)):
                parts.append(self._technical_to_phrase(rule, "buy"))

        for rule in sell_rules.get("fundamentals", []):
            if isinstance(rule, dict) and bool(rule.get("enabled", True)):
                parts.append(self._rule_to_phrase(rule, "sell"))
        for rule in sell_rules.get("technicals", []):
            if isinstance(rule, dict) and bool(rule.get("enabled", True)):
                parts.append(self._technical_to_phrase(rule, "sell"))

        if not parts:
            parts.extend(self._parse_condition_text(str(config.get("buyFactorConditions", "")), "buy"))
            parts.extend(self._parse_condition_text(str(config.get("sellFactorConditions", "")), "sell"))

        if not parts:
            parts.append("总市值>20000000")
            parts.append("股价站上5日线买入")
            parts.append("MACD金叉买入")
            parts.append("MACD死叉卖出")

        holding_period = int(self._safe_float(config.get("holdingPeriod"), 0))
        if holding_period > 0:
            parts.append(f"持有{holding_period}天")

        benchmark = str(config.get("benchmark", "000300.SH")).strip()
        if benchmark:
            parts.append(f"基准设置为{self._benchmark_map.get(benchmark, benchmark)}")

        return "示例：" + "，".join(parts) + "。"

    def _recommend_strategy_ideas(self, payload: dict[str, Any]) -> dict[str, Any]:
        tasks = payload.get("backtest_tasks", [])
        if not isinstance(tasks, list):
            tasks = []
        completed = [item for item in tasks if isinstance(item, dict) and item.get("result")]
        completed.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)

        if completed:
            best_task = max(
                completed,
                key=lambda item: (
                    self._safe_float(item.get("result", {}).get("kpis", {}).get("totalReturn"), -9e9)
                    - self._safe_float(item.get("result", {}).get("kpis", {}).get("maxDrawdown"), 0) * 0.6
                    + self._safe_float(item.get("result", {}).get("kpis", {}).get("sharpeRatio"), 0) * 0.08
                ),
            )
        else:
            best_task = {
                "run_id": "",
                "template_id": payload.get("template_id", "combo_01"),
                "request": {"user_config": payload.get("current_config", {})},
                "result": {"kpis": {}},
            }

        best_result = best_task.get("result", {}) if isinstance(best_task, dict) else {}
        best_kpis = best_result.get("kpis", {}) if isinstance(best_result, dict) else {}
        best_config = {}
        if isinstance(best_task, dict):
            request = best_task.get("request", {})
            if isinstance(request, dict) and isinstance(request.get("user_config"), dict):
                best_config = dict(request.get("user_config", {}))
        if not best_config:
            best_config = dict(payload.get("current_config", {}))

        total_return = self._safe_float(best_kpis.get("totalReturn"))
        max_drawdown = self._safe_float(best_kpis.get("maxDrawdown"))
        sharpe_ratio = self._safe_float(best_kpis.get("sharpeRatio"))
        best_hold = max(10, int(self._safe_float(best_config.get("holdingPeriod"), 60)))
        benchmark = self._benchmark_map.get(str(best_config.get("benchmark", "000300.SH")), "沪深300")

        current_summary = {
            "task_count": len(tasks),
            "completed_count": len(completed),
            "best_run_id": str(best_task.get("run_id", "")),
            "best_template_id": str(best_task.get("template_id", payload.get("template_id", "combo_01"))),
            "narrative": (
                f"当前共参考 {len(tasks)} 个任务，其中 {len(completed)} 个已有结果。"
                f"表现最好的任务总收益约 {total_return * 100:.2f}% ，最大回撤约 {max_drawdown * 100:.2f}% ，"
                f"夏普约 {sharpe_ratio:.2f}。"
            ),
            "highlights": [
                "优先沿着已验证有效的买入逻辑做增强，再补足更明确的卖出条件。",
                "如果当前策略收益不错但回撤偏大，优先缩短持有周期或增加趋势型卖出条件。",
                "如果当前策略稳定但进攻性不足，可以保留核心过滤因子，改成更快的趋势触发。 ",
            ],
            "best_metrics": {
                "totalReturn": total_return,
                "maxDrawdown": max_drawdown,
                "sharpeRatio": sharpe_ratio,
            },
        }

        base_example = self._config_to_semantic_text(best_config)
        enhancement_examples = [
            base_example,
            f"示例：总市值>20000000，股价站上5日线买入，MACD金叉买入，MACD死叉卖出，持有{max(15, best_hold - 10)}天，基准设置为{benchmark}。",
            f"示例：总市值>20000000，成交额>500000000，股价站上10日线买入，股价跌破5日线卖出，持有{best_hold}天，基准设置为{benchmark}。",
        ]
        diversified_examples = [
            "示例：市盈率<30，KDJ金叉买入，KDJ死叉卖出，持有20天，基准设置为沪深300。",
            "示例：成交额>500000000，MACD金叉买入，MACD死叉卖出，持有15天，基准设置为沪深300。",
            "示例：总市值>20000000，股价站上20日线买入，股价跌破10日线卖出，持有30天，基准设置为沪深300。",
        ]

        return {
            "summary": current_summary,
            "enhancement_examples": enhancement_examples,
            "diversified_examples": diversified_examples,
        }

    def _normalize_date(self, raw: str) -> str:
        text = raw.replace("-", ".").replace("/", ".")
        parts = text.split(".")
        if len(parts) == 3:
            return f"{parts[0]}.{parts[1].zfill(2)}.{parts[2].zfill(2)}"
        return raw

    def chat(self, message: str, current_config: dict[str, Any] | None = None) -> dict[str, Any]:
        current = dict(current_config or {})
        text = message.strip()
        patch: dict[str, Any] = {}
        actions: list[str] = []
        trigger_run = False

        blocked_reason = self._match_out_of_scope_reason(text)
        if blocked_reason:
            return {
                "allowed_actions": self._allowed_actions,
                "blocked": True,
                "reason": f"请求超出当前回测产品范围：{blocked_reason}",
                "config_patch": {},
                "hint": "当前仅支持参数修改、因子调整、模板切换与回测触发。",
                "examples": self.get_chat_examples(),
            }

        if "个股择时" in text:
            patch["template_id"] = "timing_13"
            actions.append("切模板")
        elif "策略1" in text or "组合1" in text:
            patch["template_id"] = "combo_01"
            actions.append("切模板")
        elif "策略2" in text or "组合2" in text:
            patch["template_id"] = "combo_02"
            actions.append("切模板")
        elif "策略3" in text or "组合3" in text:
            patch["template_id"] = "combo_03"
            actions.append("切模板")

        date_match = re.search(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2}).{0,6}(?:到|至|-).{0,6}(\d{4}[-./]\d{1,2}[-./]\d{1,2})", text)
        if date_match:
            patch["startDate"] = self._normalize_date(date_match.group(1))
            patch["endDate"] = self._normalize_date(date_match.group(2))
            actions.append("改区间")

        if "沪深300" in text or "000300" in text:
            patch["benchmark"] = "000300.SH"
            actions.append("改基准")
        elif "万科A" in text or "000002" in text:
            patch["benchmark"] = "000002.SZ"
            actions.append("改基准")

        max_pos_match = re.search(r"最大持股(?:数|股数)?\D*(\d+)", text)
        if max_pos_match:
            patch["maxPositionLimit"] = int(max_pos_match.group(1))
            actions.append("改参数")

        daily_buy_match = re.search(r"单日最大买入(?:数|股票数)?\D*(\d+)", text)
        if daily_buy_match:
            patch["dailyBuyCountLimit"] = int(daily_buy_match.group(1))
            actions.append("改参数")

        hold_match = re.search(r"持股周期\D*(\d+)", text)
        if hold_match:
            patch["holdingPeriod"] = int(hold_match.group(1))
            actions.append("改参数")

        cash_match = re.search(r"资金(?:量)?\D*(\d{5,})", text)
        if cash_match:
            patch["cash"] = float(cash_match.group(1))
            actions.append("改参数")

        if "市盈率" in text:
            buy_factors = list(current.get("buyFactors", []))
            if "pe" not in buy_factors:
                buy_factors.append("pe")
            patch["buyFactors"] = buy_factors
            base_cond = str(current.get("buyFactorConditions", "")).strip()
            cond = "pe < 80"
            patch["buyFactorConditions"] = f"({base_cond}) and {cond}" if base_cond else cond
            actions.append("改因子")

        if "总市值" in text:
            buy_factors = list(patch.get("buyFactors", current.get("buyFactors", [])))
            if "total_mv" not in buy_factors:
                buy_factors.append("total_mv")
            patch["buyFactors"] = buy_factors
            base_cond = str(patch.get("buyFactorConditions", current.get("buyFactorConditions", ""))).strip()
            cond = "total_mv < 12000000"
            patch["buyFactorConditions"] = f"({base_cond}) and {cond}" if base_cond else cond
            actions.append("改因子")

        if "5日线" in text or "MA5" in text:
            buy_factors = list(patch.get("buyFactors", current.get("buyFactors", [])))
            if "close" not in buy_factors:
                buy_factors.append("close")
            if "ma5" not in buy_factors:
                buy_factors.append("ma5")
            patch["buyFactors"] = buy_factors
            base_cond = str(patch.get("buyFactorConditions", current.get("buyFactorConditions", ""))).strip()
            cond = "close > ma5"
            patch["buyFactorConditions"] = f"({base_cond}) and {cond}" if base_cond else cond
            actions.append("改因子")

        if "MACD死叉" in text:
            sell_factors = list(current.get("sellFactors", []))
            if "macdDeadCross" not in sell_factors:
                sell_factors.append("macdDeadCross")
            patch["sellFactors"] = sell_factors
            patch["sellFactorConditions"] = "macdDeadCross == 1"
            actions.append("改因子")

        if "回测" in text or "运行" in text:
            trigger_run = True
            actions.append("触发回测")

        if not patch and not trigger_run:
            return {
                "allowed_actions": self._allowed_actions,
                "blocked": False,
                "config_patch": {},
                "trigger_run": False,
                "hint": "我可以帮你改参数、改因子、改基准、改区间或切换模板。",
                "examples": self.get_chat_examples(),
            }

        return {
            "allowed_actions": self._allowed_actions,
            "blocked": False,
            "config_patch": patch,
            "trigger_run": trigger_run,
            "applied_actions": sorted(set(actions)),
            "hint": "已生成受限范围内的配置补丁，可直接应用后回测。",
            "examples": self.get_chat_examples(),
        }

    def _match_out_of_scope_reason(self, text: str) -> str | None:
        for keyword in self._out_of_scope_keywords:
            if keyword in text:
                return keyword

        for pattern, reason in self._out_of_scope_patterns:
            if pattern.search(text):
                return reason

        return None

    def get_chat_examples(self) -> list[str]:
        return [
            "把回测区间改成 2023-01-01 到 2023-12-31",
            "把最大持股数调到10，单日最大买入调到3",
            "基准改成沪深300，并加入市盈率和总市值条件",
            "切换到个股择时模板，股票用600519.SH，然后运行回测",
        ]
