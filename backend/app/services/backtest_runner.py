from __future__ import annotations

import random
from datetime import datetime
import time
from typing import Any, Callable

import pandas as pd

from app.services.ddb_connection_manager import DolphinDBConnectionManager
from app.services.result_serializer import ResultSerializer
from app.services.script_registry import DolphinDBScriptRegistry, TemplateDefinition


class BacktestRunner:
    _unsupported_timing_indicators: set[str] = {"MACD", "KDJ", "RSI", "BOLL"}
    _unsupported_timing_signals: dict[str, set[str]] = {
        # These signals are implemented with order-sensitive expressions in framework scripts
        # and cannot be pushed down in distributed where clauses.
        "MACD": {"上移", "下移"},
        "KDJ": {"拐头向上", "拐头向下"},
        "RSI": {"拐头向上", "拐头向下"},
    }

    def __init__(
        self,
        connection: DolphinDBConnectionManager,
        registry: DolphinDBScriptRegistry,
        serializer: ResultSerializer,
    ) -> None:
        self._connection = connection
        self._registry = registry
        self._serializer = serializer

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _is_not_data_node_error(self, text: str) -> bool:
        lowered = (text or "").lower()
        markers = [
            "isn't a data node",
            "is not a data node",
            "can't run function [loadtable]",
            "cannot run function [loadtable]",
            "not a data node",
            "不是数据节点",
        ]
        return any(token in lowered for token in markers)

    def _is_transient_connection_error(self, text: str) -> bool:
        lowered = (text or "").lower()
        markers = [
            "socket is disconnected",
            "socket is closed",
            "connection has been closed",
            "failed to read response header",
            "io error type 1",
            "network is unreachable",
            "timed out",
            "connection reset",
            "broken pipe",
        ]
        return any(token in lowered for token in markers)

    def _ddb_literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        if isinstance(value, (list, tuple)):
            return "[" + ",".join(self._ddb_literal(v) for v in value) + "]"
        if isinstance(value, dict):
            items = [f"`{k}:{self._ddb_literal(v)}" for k, v in value.items()]
            return "{" + ",".join(items) + "}"
        raise TypeError(f"Unsupported config value type: {type(value)}")

    def _build_user_config_literal(self, user_config: dict[str, Any]) -> str:
        items = [f"`{key}:{self._ddb_literal(value)}" for key, value in user_config.items()]
        return "{" + ",\n".join(items) + "}"

    def _ensure_date_order(self, user_config: dict[str, Any]) -> None:
        start = str(user_config.get("startDate", "")).replace(".", "-")
        end = str(user_config.get("endDate", "")).replace(".", "-")
        if not start or not end:
            raise ValueError("startDate/endDate are required.")
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError("startDate must be earlier than or equal to endDate.")

    def _validate_combo_config(
        self,
        user_config: dict[str, Any],
        auto_fallback_benchmark: bool,
        execute_fn: Callable[[str], Any] | None = None,
    ) -> list[str]:
        warnings: list[str] = []
        run_script = execute_fn or (lambda script: self._connection.execute(script, require_data_node=True))
        self._ensure_date_order(user_config)
        if float(user_config.get("cash", 0)) <= 0:
            raise ValueError("cash must be positive.")

        max_position = int(user_config.get("maxPositionLimit", 0))
        daily_buy = int(user_config.get("dailyBuyCountLimit", 0))
        if max_position <= 0 or daily_buy <= 0:
            raise ValueError("maxPositionLimit and dailyBuyCountLimit must be > 0.")
        if daily_buy > max_position:
            raise ValueError("dailyBuyCountLimit cannot exceed maxPositionLimit.")

        columns_raw = run_script(
            'exec name from schema(loadTable("dfs://day_singal","day_singal")).colDefs',
        )
        if hasattr(columns_raw, "tolist"):
            day_columns = set(columns_raw.tolist())
        elif isinstance(columns_raw, list):
            day_columns = set(columns_raw)
        else:
            day_columns = {str(columns_raw)}
        all_factor_fields = (
            list(user_config.get("buyFactors", []))
            + list(user_config.get("sellFactors", []))
            + list(user_config.get("buyPriority", []))
            + list(user_config.get("sellPriority", []))
        )
        missing = [field for field in all_factor_fields if field and field not in day_columns]
        if missing:
            raise ValueError(f"Missing factor fields in day_singal: {sorted(set(missing))}")

        benchmark = str(user_config.get("benchmark", "000002.SZ"))
        bench_count = int(
            run_script(f'exec count(*) from loadTable("dfs://minute_singal","minute_singal") where ts_code="{benchmark}"')
        )
        if bench_count <= 0:
            if auto_fallback_benchmark:
                user_config["benchmark"] = "000002.SZ"
                warnings.append(f"Benchmark {benchmark} has no minute data. Fallback to 000002.SZ.")
            else:
                raise ValueError(f"Benchmark {benchmark} has no minute data in minute_singal.")
        return warnings

    def _format_numeric(self, raw: Any) -> str:
        try:
            num = float(raw)
            if num.is_integer():
                return str(int(num))
            return f"{num:.8f}".rstrip("0").rstrip(".")
        except Exception:
            return str(raw)

    def _build_technical_expr(
        self,
        rule: dict[str, Any],
        day_columns: set[str],
    ) -> tuple[str | None, list[str], str]:
        rtype = str(rule.get("type", "")).strip()
        if not rtype:
            return None, [], ""

        if rtype == "ma_above":
            period = int(rule.get("period", 5))
            ma_field = f"ma{period}"
            if ma_field not in day_columns:
                return None, [], f"{ma_field} not found in day_singal"
            return f"close > {ma_field}", ["close", ma_field], ""
        if rtype == "ma_below":
            period = int(rule.get("period", 5))
            ma_field = f"ma{period}"
            if ma_field not in day_columns:
                return None, [], f"{ma_field} not found in day_singal"
            return f"close < {ma_field}", ["close", ma_field], ""
        if rtype == "ma_bull_arrangement":
            needed = ["ma5", "ma10", "ma20"]
            missing = [x for x in needed if x not in day_columns]
            if missing:
                return None, [], f"missing columns for ma_bull_arrangement: {missing}"
            return "ma5 > ma10 and ma10 > ma20", needed, ""
        if rtype == "macd_golden":
            if "macdDeadCross" not in day_columns:
                return None, [], "macdDeadCross not found in day_singal"
            return "macdDeadCross == 0", ["macdDeadCross"], ""
        if rtype == "macd_dead":
            if "macdDeadCross" not in day_columns:
                return None, [], "macdDeadCross not found in day_singal"
            return "macdDeadCross == 1", ["macdDeadCross"], ""
        if rtype == "rsi_threshold":
            if "rsi12" not in day_columns:
                return None, [], "rsi12 not found in day_singal"
            op = str(rule.get("op", "<")).strip()
            if op not in ["<", "<=", ">", ">=", "==", "!="]:
                return None, [], f"unsupported rsi op: {op}"
            threshold = self._format_numeric(rule.get("value", 30))
            return f"rsi12 {op} {threshold}", ["rsi12"], ""
        if rtype == "kdj_golden":
            if "kdjDeadCross" not in day_columns:
                return None, [], "kdjDeadCross not found in day_singal"
            return "kdjDeadCross == 0", ["kdjDeadCross"], ""
        if rtype == "kdj_dead":
            if "kdjDeadCross" not in day_columns:
                return None, [], "kdjDeadCross not found in day_singal"
            return "kdjDeadCross == 1", ["kdjDeadCross"], ""
        if rtype == "boll_break_upper":
            needed = ["close", "bollBreakUpper"]
            missing = [x for x in needed if x not in day_columns]
            if missing:
                return None, [], f"missing columns for boll_break_upper: {missing}"
            return "close > bollBreakUpper", needed, ""
        if rtype == "boll_break_lower":
            needed = ["close", "bollBreakLower"]
            missing = [x for x in needed if x not in day_columns]
            if missing:
                return None, [], f"missing columns for boll_break_lower: {missing}"
            return "close < bollBreakLower", needed, ""
        if rtype == "bbi_break":
            if "breakBBI" not in day_columns:
                return None, [], "breakBBI not found in day_singal"
            return "breakBBI == 1", ["breakBBI"], ""
        return None, [], f"unsupported technical rule: {rtype}"

    def _normalize_factor_rule_set(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {"logic": "and", "fundamentals": [], "technicals": []}
        fundamentals = raw.get("fundamentals", [])
        technicals = raw.get("technicals", [])
        return {
            "logic": "or" if str(raw.get("logic", "and")).strip().lower() == "or" else "and",
            "fundamentals": fundamentals if isinstance(fundamentals, list) else [],
            "technicals": technicals if isinstance(technicals, list) else [],
        }

    def _normalize_factor_customization(self, raw: Any) -> dict[str, dict[str, Any]]:
        empty = {"logic": "and", "fundamentals": [], "technicals": []}
        if not isinstance(raw, dict):
            return {"buy": dict(empty), "sell": dict(empty)}
        if "buy" in raw or "sell" in raw:
            return {
                "buy": self._normalize_factor_rule_set(raw.get("buy")),
                "sell": self._normalize_factor_rule_set(raw.get("sell")),
            }
        return {
            "buy": self._normalize_factor_rule_set(raw),
            "sell": dict(empty),
        }

    def _build_rule_expressions(
        self,
        rule_set: dict[str, Any],
        day_columns: set[str],
        side: str,
    ) -> tuple[list[str], list[str], list[str]]:
        warnings: list[str] = []
        expressions: list[str] = []
        required_fields: list[str] = []

        for rule in rule_set.get("fundamentals", []):
            if not isinstance(rule, dict):
                continue
            if not bool(rule.get("enabled", True)):
                continue
            field = str(rule.get("field", "")).strip()
            op = str(rule.get("op", "<=")).strip()
            value = rule.get("value")
            if not field:
                continue
            if field not in day_columns:
                warnings.append(f"{side} fundamental field skipped (not found): {field}")
                continue
            if op not in ["<", "<=", ">", ">=", "==", "!="]:
                warnings.append(f"{side} fundamental field skipped (op unsupported): {field} {op}")
                continue
            expressions.append(f"{field} {op} {self._format_numeric(value)}")
            required_fields.append(field)

        for rule in rule_set.get("technicals", []):
            if not isinstance(rule, dict):
                continue
            if not bool(rule.get("enabled", True)):
                continue
            expr, fields, err = self._build_technical_expr(rule, day_columns)
            if err:
                warnings.append(f"{side} {err}")
                continue
            if expr:
                expressions.append(expr)
                required_fields.extend(fields)

        return expressions, required_fields, warnings

    def _apply_factor_customization(
        self,
        user_config: dict[str, Any],
        day_columns: set[str],
    ) -> tuple[list[str], str]:
        warnings: list[str] = []
        custom = user_config.get("factorCustomization")
        if not isinstance(custom, dict):
            return warnings, ""
        normalized = self._normalize_factor_customization(custom)

        def apply_side(side: str, factors_key: str, conditions_key: str) -> None:
            nonlocal warnings
            rule_set = normalized[side]
            logic = str(rule_set.get("logic", "and")).strip().lower()
            joiner = " and " if logic != "or" else " or "
            expressions, required_fields, side_warnings = self._build_rule_expressions(rule_set, day_columns, side)
            warnings.extend(side_warnings)
            if not expressions:
                return
            factors = list(user_config.get(factors_key, []))
            seen = set(factors)
            for field in required_fields:
                if field not in seen:
                    factors.append(field)
                    seen.add(field)
            user_config[factors_key] = factors
            user_config[conditions_key] = joiner.join(expressions)

        apply_side("buy", "buyFactors", "buyFactorConditions")
        apply_side("sell", "sellFactors", "sellFactorConditions")
        return warnings, ""

    def _validate_timing_config(self, user_config: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        self._ensure_date_order(user_config)
        if float(user_config.get("cash", 0)) <= 0:
            raise ValueError("cash must be positive.")

        factor_meta = self._registry.get_factor_meta()["timing_signal_map"]
        buy_factors = list(user_config.get("buyFactors", []))
        buy_signals = list(user_config.get("buyFactorConditions", []))
        sell_factors = list(user_config.get("sellFactors", []))
        sell_signals = list(user_config.get("sellFactorConditions", []))

        if len(buy_factors) != len(buy_signals):
            raise ValueError("buyFactors and buyFactorConditions length mismatch.")
        if len(sell_factors) != len(sell_signals):
            raise ValueError("sellFactors and sellFactorConditions length mismatch.")

        for indicator, signal in list(zip(buy_factors, buy_signals)) + list(zip(sell_factors, sell_signals)):
            if indicator not in factor_meta:
                raise ValueError(f"Unsupported indicator: {indicator}")
            if indicator in self._unsupported_timing_indicators:
                raise ValueError(
                    f"Indicator '{indicator}' is currently unsupported in distributed timing engine."
                )
            if signal not in factor_meta[indicator]:
                raise ValueError(f"Unsupported signal for {indicator}: {signal}")
            blocked = self._unsupported_timing_signals.get(indicator, set())
            if signal in blocked:
                raise ValueError(
                    f"Signal '{signal}' for {indicator} is currently unsupported in distributed timing engine."
                )
        if not buy_factors:
            raise ValueError("No supported buy factors remain after timing signal alignment.")
        return warnings

    def _build_exec_script(self, template: TemplateDefinition, user_config: dict[str, Any], run_id: str) -> str:
        strategy_name = f'dolphindb_{template.template_id}_{run_id}_{random.randint(1000, 9999)}'
        user_config_literal = self._build_user_config_literal(user_config)
        if template.strategy_type == "combo":
            return f"""
userConfig={user_config_literal};
resRaw=runStrategy_dayK_compo("{strategy_name}", userConfig);
resRaw
"""
        return f"""
userConfig={user_config_literal};
resRaw=runDailySingleStockTimingStrategy("{strategy_name}", userConfig);
resRaw
"""

    def _sanitize_framework_script(self, script_text: str) -> tuple[str, list[str]]:
        warnings: list[str] = []
        normalized = script_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")

        split_idx = len(lines)
        split_reason = ""
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("def test"):
                split_idx = idx
                split_reason = "test helper functions"
                break
            if stripped.startswith("//////////////////////////////////////////////////////////////////////////////////////////////"):
                split_idx = min(split_idx, idx)
                split_reason = "demo section marker"
                break

        core_lines = lines[:split_idx]
        cleaned_lines: list[str] = []
        removed_view_lines = 0
        for line in core_lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                cleaned_lines.append(line)
                continue
            if "addFunctionView(" in stripped:
                removed_view_lines += 1
                continue
            if "dropFunctionView(" in stripped:
                removed_view_lines += 1
                continue
            cleaned_lines.append(line)

        if split_idx < len(lines):
            warnings.append(f"Trimmed framework script tail at line {split_idx + 1} ({split_reason}).")
        if removed_view_lines > 0:
            warnings.append(
                f"Removed {removed_view_lines} FunctionView statements in core script to avoid concurrent conflicts."
            )
        return "\n".join(cleaned_lines).rstrip() + "\n", warnings

    def _ensure_timing_signal_alignment(self, user_config: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        signal_map = self._registry.get_factor_meta().get("timing_signal_map", {})

        def to_list(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            if isinstance(value, (list, tuple)):
                return [str(x) for x in value]
            return []

        def pick_default_signal(indicator: str, options: list[str]) -> str:
            blocked = self._unsupported_timing_signals.get(indicator, set())
            for option in options:
                if option not in blocked:
                    return str(option)
            return str(options[0]) if options else ""

        def align(side: str, factors_key: str, signals_key: str) -> None:
            factors = to_list(user_config.get(factors_key))
            signals = to_list(user_config.get(signals_key))
            original_signal_len = len(signals)
            if not factors and not signals:
                user_config[factors_key] = []
                user_config[signals_key] = []
                return
            if len(signals) < len(factors):
                for idx in range(len(signals), len(factors)):
                    indicator = factors[idx]
                    options = signal_map.get(indicator, [])
                    if options:
                        signals.append(pick_default_signal(indicator, options))
                    else:
                        signals.append("")
                warnings.append(
                    f"{side} signals were shorter than factors; auto-filled defaults for {len(factors) - original_signal_len} items."
                )
            if len(signals) > len(factors):
                signals = signals[: len(factors)]
                warnings.append(f"{side} signals were longer than factors; truncated to match factors length.")
            for idx, indicator in enumerate(factors):
                options = signal_map.get(indicator, [])
                if not options:
                    continue
                current_signal = signals[idx].strip() if idx < len(signals) else ""
                blocked = self._unsupported_timing_signals.get(indicator, set())
                if current_signal and current_signal in options and current_signal not in blocked:
                    continue
                signals[idx] = pick_default_signal(indicator, options)
                if current_signal:
                    warnings.append(
                        f"{side} signal '{current_signal}' for indicator '{indicator}' is unsupported; replaced with default."
                    )
            # Remove pairs with empty factor or signal.
            paired = [(f.strip(), s.strip()) for f, s in zip(factors, signals) if f.strip() and s.strip()]
            user_config[factors_key] = [f for f, _ in paired]
            user_config[signals_key] = [s for _, s in paired]

        align("buy", "buyFactors", "buyFactorConditions")
        align("sell", "sellFactors", "sellFactorConditions")
        return warnings

    def _ensure_combo_equity(
        self,
        raw: Any,
        user_config: dict[str, Any],
        execute_fn: Callable[[str], Any],
    ) -> tuple[Any, list[str]]:
        warnings: list[str] = []
        if not isinstance(raw, dict):
            return raw, warnings
        daily = raw.get("dailyTotalPortfolios")
        if isinstance(daily, pd.DataFrame) and not daily.empty:
            return raw, warnings

        start = str(user_config.get("startDate", "2021.01.01")).replace("-", ".")
        end = str(user_config.get("endDate", "2021.12.31")).replace("-", ".")
        benchmark = str(user_config.get("benchmark", "000002.SZ"))
        try:
            cash = float(user_config.get("cash", 1000000.0))
        except Exception:
            cash = 1000000.0
        script = f"""
bench = select date(trade_time) as tradeDate, last(close) as benchmarkClose
from loadTable("dfs://minute_singal","minute_singal")
where ts_code="{benchmark}" and date(trade_time) between date("{start}") : date("{end}")
group by date(trade_time) order by tradeDate;
if(bench.size() == 0){{
    bench = table([date("{start}"), date("{end}")] as tradeDate, [1.0,1.0] as benchmarkClose);
}}
update bench set benchmarkNetValue = benchmarkClose \\ benchmarkClose[0];
update bench set totalPortfolios = {cash};
update bench set totalEquity = {cash};
update bench set netValue = 1.0;
update bench set cash = {cash};
update bench set totalMarketValue = 0.0;
bench
"""
        try:
            bench = execute_fn(script)
            if isinstance(bench, pd.DataFrame) and not bench.empty:
                raw["dailyTotalPortfolios"] = bench
                warnings.append("dailyTotalPortfolios was empty; generated fallback equity curve from benchmark series.")
        except Exception as exc:
            warnings.append(f"Failed to generate fallback equity curve: {exc}")
        return raw, warnings

    def run(
        self,
        run_id: str,
        template_id: str,
        user_config: dict[str, Any] | None = None,
        ai_patch: dict[str, Any] | None = None,
        auto_fallback_benchmark: bool = True,
    ) -> dict[str, Any]:
        template = self._registry.get_template(template_id)
        merged = self._deep_merge(template.default_config, user_config or {})
        if ai_patch:
            merged = self._deep_merge(merged, ai_patch)

        execution_started = datetime.utcnow()
        perf_start = time.perf_counter()
        factor_code = ""
        warnings: list[str] = []
        raw: Any = {}
        exec_script = ""
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            session = self._connection.open_task_session(require_data_node=True, force_probe=attempt > 1)

            def run_script(script: str) -> Any:
                nonlocal session
                for _ in range(3):
                    try:
                        return session.run(script)
                    except Exception as exc:
                        text = str(exc)
                        if self._is_not_data_node_error(text) or self._is_transient_connection_error(text):
                            try:
                                session.close()
                            except Exception:
                                pass
                            session = self._connection.open_task_session(require_data_node=True, force_probe=True)
                            continue
                        raise
                raise RuntimeError("Failed to execute script on a valid DolphinDB data node after retries.")

            try:
                attempt_warnings: list[str] = []
                factor_code = ""
                if template.strategy_type == "combo":
                    attempt_warnings.extend(
                        self._validate_combo_config(
                            merged,
                            auto_fallback_benchmark=auto_fallback_benchmark,
                            execute_fn=run_script,
                        )
                    )
                    columns_raw = run_script('exec name from schema(loadTable("dfs://day_singal","day_singal")).colDefs')
                    if hasattr(columns_raw, "tolist"):
                        day_columns = set(columns_raw.tolist())
                    elif isinstance(columns_raw, list):
                        day_columns = set(columns_raw)
                    else:
                        day_columns = {str(columns_raw)}
                    custom_warnings, factor_code = self._apply_factor_customization(merged, day_columns)
                    attempt_warnings.extend(custom_warnings)
                else:
                    attempt_warnings.extend(self._ensure_timing_signal_alignment(merged))
                    attempt_warnings.extend(self._validate_timing_config(merged))

                script_text = self._registry.load_script(template_id)
                script_text, script_warnings = self._sanitize_framework_script(script_text)
                attempt_warnings.extend(script_warnings)
                run_script(script_text)
                exec_script = self._build_exec_script(template, merged, run_id=run_id)
                raw = run_script(exec_script)
                if template.strategy_type == "combo":
                    raw, equity_warnings = self._ensure_combo_equity(raw, merged, run_script)
                    attempt_warnings.extend(equity_warnings)
                warnings = attempt_warnings
                if attempt > 1:
                    warnings.append(f"Task recovered after transient DolphinDB connection issue (attempt {attempt}).")
                break
            except Exception as exc:
                text = str(exc)
                if attempt < max_attempts and self._is_transient_connection_error(text):
                    warnings = [f"Transient DolphinDB error detected, retrying run (attempt {attempt + 1}/{max_attempts})."]
                    time.sleep(1.0)
                    continue
                raise
            finally:
                try:
                    session.close()
                except Exception:
                    pass
        execution_finished = datetime.utcnow()
        duration_ms = round((time.perf_counter() - perf_start) * 1000, 3)

        script_name = self._registry.script_filename(template_id)
        framework_02 = self._registry.load_script("combo_02")
        code_files: list[dict[str, Any]] = []
        if factor_code.strip():
            code_files.append(
                {
                    "name": "00_factor_processing.dos",
                    "kind": "factor_processing",
                    "included": True,
                    "content": factor_code,
                }
            )
        else:
            code_files.append(
                {
                    "name": "00_factor_processing.dos",
                    "kind": "factor_processing",
                    "included": False,
                    "content": "",
                }
            )
        code_files.append(
            {
                "name": "01_backtest_run.dos",
                "kind": "backtest_run",
                "included": True,
                "content": f"// source script: {script_name}\n{exec_script}",
            }
        )
        code_files.append(
            {
                "name": "02_backtest_framework_template_02.dos",
                "kind": "framework_02",
                "included": True,
                "content": framework_02,
            }
        )

        execution = {
            "started_at": execution_started.isoformat() + "Z",
            "finished_at": execution_finished.isoformat() + "Z",
            "duration_ms": duration_ms,
        }
        return self._serializer.serialize(
            run_id=run_id,
            template_id=template_id,
            raw=raw,
            warnings=warnings,
            execution=execution,
            code_files=code_files,
        )

    def get_trade_page(
        self,
        result: dict[str, Any],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = max(min(page_size, 1000), 1)
        trades = list(result.get("trades", []))
        total = len(trades)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": trades[start:end],
        }

    def to_trade_csv(self, result: dict[str, Any]) -> str:
        trades = list(result.get("trades", []))
        if not trades:
            return ""
        headers = list(trades[0].keys())
        rows = [",".join(headers)]
        for item in trades:
            row = []
            for key in headers:
                value = str(item.get(key, ""))
                if "," in value or '"' in value:
                    value = '"' + value.replace('"', '""') + '"'
                row.append(value)
            rows.append(",".join(row))
        return "\n".join(rows)
