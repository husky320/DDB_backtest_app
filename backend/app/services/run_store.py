from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.storage import read_json, write_json
from app.services.error_formatter import format_backtest_error


class BacktestRunStore:
    def __init__(self, store_file: Path | None = None, max_items: int = 3000) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}
        self._store_file = store_file
        self._max_items = max(100, int(max_items))
        self._load()

    def _load(self) -> None:
        if self._store_file is None:
            return
        payload = read_json(self._store_file, {})
        rows = payload.get("runs", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            return
        needs_persist = False
        for item in rows:
            if not isinstance(item, dict):
                continue
            run_id = str(item.get("run_id", "")).strip()
            if not run_id:
                continue
            sanitized_item, changed = self._sanitize_item_for_storage(item)
            self._runs[run_id] = sanitized_item
            needs_persist = needs_persist or changed
        if needs_persist:
            self._persist_locked()

    def _persist_locked(self) -> None:
        if self._store_file is None:
            return
        rows = list(self._runs.values())
        rows.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        if len(rows) > self._max_items:
            rows = rows[: self._max_items]
            self._runs = {str(item["run_id"]): item for item in rows if isinstance(item, dict) and item.get("run_id")}
        write_json(self._store_file, {"runs": rows})

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _normalize_rule_label(self, raw: Any) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        mapping = {
            "total_mv": "总市值",
            "pe": "市盈率",
            "amount": "成交额",
            "close": "收盘价",
            "ma5": "MA5",
            "ma10": "MA10",
            "ma20": "MA20",
            "ma30": "MA30",
            "macdDeadCross": "MACD死叉",
            "kdjDeadCross": "KDJ死叉",
            "breakBBI": "BBI破位",
            "pct_chg": "涨跌幅",
        }
        return mapping.get(text, text)

    def _collect_custom_rule_labels(self, side_key: str, custom: dict[str, Any]) -> list[str]:
        if side_key in custom and isinstance(custom.get(side_key), dict):
            rule_set = custom.get(side_key, {})
        else:
            rule_set = custom if side_key == "buy" else {}
        if not isinstance(rule_set, dict):
            return []
        labels: list[str] = []
        fundamentals = rule_set.get("fundamentals", [])
        technicals = rule_set.get("technicals", [])
        if isinstance(fundamentals, list):
            for item in fundamentals:
                if not isinstance(item, dict) or item.get("enabled") is False:
                    continue
                label = self._normalize_rule_label(item.get("label") or item.get("field"))
                if label:
                    labels.append(label)
        if isinstance(technicals, list):
            for item in technicals:
                if not isinstance(item, dict) or item.get("enabled") is False:
                    continue
                label = self._normalize_rule_label(item.get("label") or item.get("type"))
                if label:
                    labels.append(label)
        return labels

    def _build_strategy_label(self, template_id: str, request_payload: dict[str, Any]) -> str:
        config: dict[str, Any] = {}
        user_config = request_payload.get("user_config", {})
        ai_patch = request_payload.get("ai_patch", {})
        if isinstance(user_config, dict):
            config.update(user_config)
        if isinstance(ai_patch, dict):
            config.update(ai_patch)

        buy_labels: list[str] = []
        sell_labels: list[str] = []

        custom = config.get("factorCustomization")
        if isinstance(custom, dict):
            buy_labels.extend(self._collect_custom_rule_labels("buy", custom))
            sell_labels.extend(self._collect_custom_rule_labels("sell", custom))

        if not buy_labels:
            buy_factors = config.get("buyFactors", [])
            if isinstance(buy_factors, list):
                buy_labels.extend(self._normalize_rule_label(item) for item in buy_factors if str(item).strip())
        if not sell_labels:
            sell_factors = config.get("sellFactors", [])
            if isinstance(sell_factors, list):
                sell_labels.extend(self._normalize_rule_label(item) for item in sell_factors if str(item).strip())

        buy_labels = [item for idx, item in enumerate(buy_labels) if item and item not in buy_labels[:idx]]
        sell_labels = [item for idx, item in enumerate(sell_labels) if item and item not in sell_labels[:idx]]

        if buy_labels or sell_labels:
            buy_text = " + ".join(buy_labels[:2]) if buy_labels else "默认买入"
            sell_text = " + ".join(sell_labels[:2]) if sell_labels else "默认卖出"
            return f"{buy_text} / {sell_text}"

        fallback_map = {
            "combo_01": "组合策略",
            "combo_02": "组合策略",
            "combo_03": "组合策略",
            "timing_13": "个股择时策略",
        }
        return fallback_map.get(template_id, "回测策略")

    def _enrich_item_locked(self, item: dict[str, Any]) -> dict[str, Any]:
        if not item.get("strategy_label"):
            item["strategy_label"] = self._build_strategy_label(str(item.get("template_id", "")), item.get("request", {}))
        return item

    def _compact_result_for_storage(self, result: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        compacted = dict(result)
        changed = False
        if compacted.get("tables"):
            compacted["tables"] = {}
            changed = True
        elif "tables" in compacted and not isinstance(compacted.get("tables"), dict):
            compacted["tables"] = {}
            changed = True
        return compacted, changed

    def _sanitize_item_for_storage(self, item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        sanitized = dict(item)
        changed = False
        result = sanitized.get("result")
        if isinstance(result, dict):
            compacted_result, result_changed = self._compact_result_for_storage(result)
            if result_changed:
                sanitized["result"] = compacted_result
                changed = True
        return sanitized, changed

    def _snapshot_item(
        self,
        item: dict[str, Any],
        *,
        include_trades: bool,
        include_tables: bool,
    ) -> dict[str, Any]:
        snapshot = dict(item)
        result = snapshot.get("result")
        if not isinstance(result, dict):
            return snapshot

        result_snapshot = deepcopy(result)
        if not include_trades:
            result_snapshot["trades"] = []
        if not include_tables:
            result_snapshot["tables"] = {}
        snapshot["result"] = result_snapshot
        return snapshot

    def create(self, run_id: str, template_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        item = {
            "run_id": run_id,
            "template_id": template_id,
            "strategy_label": self._build_strategy_label(template_id, request_payload),
            "status": "running",
            "error": None,
            "result": None,
            "request": request_payload,
            "created_at": now,
            "started_at": now,
            "finished_at": None,
            "duration_ms": None,
            "error_detail": None,
            "error_info": None,
        }
        with self._lock:
            self._runs[run_id] = item
            self._persist_locked()
        return item

    def complete(self, run_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            if run_id in self._runs:
                item = self._enrich_item_locked(self._runs[run_id])
                execution = result.get("execution", {}) if isinstance(result, dict) else {}
                stored_result = result
                if isinstance(result, dict):
                    stored_result, _ = self._compact_result_for_storage(result)
                item["status"] = "degraded" if bool(result.get("degraded")) else "completed"
                item["result"] = stored_result
                item["error"] = None
                item["error_detail"] = None
                item["error_info"] = None
                item["finished_at"] = execution.get("finished_at") or self._now()
                item["duration_ms"] = execution.get("duration_ms")
                self._persist_locked()

    def fail(self, run_id: str, error: str, error_info: dict[str, Any] | None = None) -> None:
        with self._lock:
            if run_id in self._runs:
                item = self._enrich_item_locked(self._runs[run_id])
                parsed = error_info or format_backtest_error(error)
                item["status"] = "failed"
                item["error"] = parsed.get("summary") or error
                item["error_detail"] = error
                item["error_info"] = parsed
                item["finished_at"] = self._now()
                self._persist_locked()

    def get(
        self,
        run_id: str,
        *,
        include_trades: bool = True,
        include_tables: bool = False,
    ) -> dict[str, Any] | None:
        with self._lock:
            item = self._runs.get(run_id)
            if item is None:
                return None
            item = self._enrich_item_locked(item)
            return self._snapshot_item(item, include_trades=include_trades, include_tables=include_tables)

    def delete(self, run_id: str) -> bool:
        with self._lock:
            if run_id not in self._runs:
                return False
            del self._runs[run_id]
            self._persist_locked()
            return True

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = []
            for item in self._runs.values():
                item = self._enrich_item_locked(item)
                rows.append(
                    {
                        "run_id": item["run_id"],
                        "template_id": item["template_id"],
                        "strategy_label": item.get("strategy_label"),
                        "status": item["status"],
                        "error": item["error"],
                        "error_info": item.get("error_info"),
                        "created_at": item.get("created_at"),
                        "started_at": item.get("started_at"),
                        "finished_at": item.get("finished_at"),
                        "duration_ms": item.get("duration_ms"),
                    }
                )
        rows.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return rows[: max(1, limit)]
