from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


class ResultSerializer:
    def normalize_value(self, value: Any) -> Any:
        if isinstance(value, (datetime, date, pd.Timestamp)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, (np.ndarray, list, tuple)):
            return [self.normalize_value(x) for x in value]
        if isinstance(value, dict):
            return {str(k): self.normalize_value(v) for k, v in value.items()}
        return value

    def df_to_records(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []
        rows: list[dict[str, Any]] = []
        for raw_row in df.to_dict("records"):
            row = {str(k): self.normalize_value(v) for k, v in raw_row.items()}
            rows.append(row)
        return rows

    def _extract_kpis(self, return_summary_records: list[dict[str, Any]]) -> dict[str, Any]:
        if not return_summary_records:
            return {}
        row = return_summary_records[0]
        wanted = [
            "totalReturn",
            "annualReturn",
            "maxDrawdown",
            "sharpeRatio",
            "winRate",
            "numTrades",
            "turnoverRate",
            "totalEquity",
        ]
        kpis = {}
        for key in wanted:
            if key in row:
                kpis[key] = row[key]
        if "winRate" not in kpis and "dailyWinningRate" in row:
            kpis["winRate"] = row["dailyWinningRate"]
        return kpis

    def _normalize_series(self, values: list[Any]) -> list[float | None]:
        first: float | None = None
        out: list[float | None] = []
        for raw in values:
            if raw is None:
                out.append(None)
                continue
            try:
                val = float(raw)
            except Exception:
                out.append(None)
                continue
            if first is None and val != 0:
                first = val
            if first is None:
                out.append(None)
            else:
                out.append(val / first)
        return out

    def _extract_equity(self, daily_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not daily_records:
            return []
        dates: list[Any] = []
        strategy_raw: list[Any] = []
        benchmark_raw: list[Any] = []
        for row in daily_records:
            dates.append(row.get("tradeDate") or row.get("date"))
            strategy_raw.append(row.get("totalPortfolios") or row.get("totalEquity") or row.get("netValue"))
            benchmark_raw.append(row.get("benchmarkNetValue"))
        strategy_norm = self._normalize_series(strategy_raw)
        benchmark_norm = self._normalize_series(benchmark_raw)
        out: list[dict[str, Any]] = []
        for idx, trade_date in enumerate(dates):
            out.append({"tradeDate": trade_date, "portfolioValue": strategy_norm[idx], "benchmarkValue": benchmark_norm[idx]})
        return out

    def serialize(
        self,
        run_id: str,
        template_id: str,
        raw: Any,
        warnings: list[str] | None = None,
        execution: dict[str, Any] | None = None,
        code_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        warnings = warnings or []
        execution = execution or {}
        code_files = code_files or []
        if not isinstance(raw, dict):
            return {
                "run_id": run_id,
                "template_id": template_id,
                "status": "completed",
                "warnings": warnings,
                "execution": execution,
                "code_files": code_files,
                "kpis": {},
                "tables": {},
                "equity": [],
            }

        tables: dict[str, list[dict[str, Any]]] = {}
        for key, value in raw.items():
            if isinstance(value, pd.DataFrame):
                tables[str(key)] = self.df_to_records(value)
            else:
                tables[str(key)] = self.normalize_value(value)

        return_summary = tables.get("returnSummary", [])
        daily_total = tables.get("dailyTotalPortfolios", [])
        trade_details = tables.get("tradeDetails", [])
        warnings_lower = " ".join(str(x).lower() for x in warnings)
        degraded_reasons: list[str] = []
        if "fallback equity curve" in warnings_lower:
            degraded_reasons.append("fallback_equity_curve")
        if not daily_total:
            degraded_reasons.append("empty_equity_table")
        if not trade_details and "fallback equity curve" in warnings_lower:
            degraded_reasons.append("no_trade_with_fallback_equity")
        degraded_reasons = sorted(set(degraded_reasons))

        return {
            "run_id": run_id,
            "template_id": template_id,
            "status": "degraded" if degraded_reasons else "completed",
            "degraded": bool(degraded_reasons),
            "degraded_reasons": degraded_reasons,
            "warnings": warnings,
            "execution": execution,
            "code_files": code_files,
            "kpis": self._extract_kpis(return_summary),
            "summary": return_summary[0] if return_summary else {},
            "equity": self._extract_equity(daily_total),
            "trades": trade_details,
            "tables": tables,
        }
