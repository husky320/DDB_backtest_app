from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    label: str
    strategy_type: str
    script_glob: str
    default_config: dict[str, Any]


class DolphinDBScriptRegistry:
    def __init__(self, script_root: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[4]
        self._script_root = script_root or self._discover_script_root(root)
        self._templates = self._build_templates()
        self._path_cache: dict[str, Path] = {}

    def _discover_script_root(self, root: Path) -> Path:
        preferred = root / "DolphinDB" / "DDB_BT"
        if preferred.exists():
            return preferred

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            candidate = entry / "DDB_BT"
            if candidate.exists():
                return candidate

        return preferred

    def _build_templates(self) -> dict[str, TemplateDefinition]:
        combo_base = {
            "buyFactors": ["total_mv", "pe", "amount", "close", "ma5"],
            "buyFactorConditions": "total_mv < 10000000 and pe < 100 and close > ma5 and amount>100000",
            "sellFactors": ["macdDeadCross"],
            "sellFactorConditions": "macdDeadCross == 1",
            "cash": 50000000.0,
            "holdingPeriod": 60,
            "industryNumRestrictions": 2,
            "benchmark": "000002.SZ",
            "percentValue": 1.0,
            "startDate": "2021.09.28",
            "endDate": "2023.09.28",
            "buyTimeType": 2,
            "buyTime": "09:50:00m",
            "sellTimeType": 2,
            "sellTime": "14:30m",
            "buyPriority": ["pct_chg"],
            "buyPriorityFactorsDiretion": [-1],
            "sellPriority": [],
            "sellPriorityFactorsDiretion": [],
            "buyRestrictions": 1,
            "dailyBuyCountLimit": 2,
            "maxPositionLimit": 5,
            "perStockPercent": 0.1,
            "isMainBoardExceed": 1,
            "isChiNextBoardExceed": 0,
            "isSTARMarketExceed": 0,
            "isBjMarketExceed": 0,
            "mainBoardExceed": 2.0,
            "ChiNextBoardExceed": 0.5,
            "STARMarketExceed": 0.5,
            "bjMarketExceed": 0.5,
            "dailySellCountLimit": 10,
            "stopOrderTimeType": 3,
            "stopOrderTiming": "14:30m",
            "isTakeProfit": 1,
            "takeProfitType": 1,
            "takeProfitValue": 9.0,
            "takeProfitRollback": 1.0,
            "isStopLoss": 1,
            "stopLossType": 0,
            "stopLossValue": 5.0,
            "stopLossRollback": 1.0,
            "stockUniverse": "all",
            "isRealTimePosIncrease": 0,
            "initPosPercent": 0.1,
            "addPosPercent": 0.1,
            "isRealTimePosReduction": 0,
            "cutPosPercent": 0.1,
        }

        return {
            "combo_01": TemplateDefinition(
                template_id="combo_01",
                label="日K组合策略-1",
                strategy_type="combo",
                script_glob="01*.dos",
                default_config=dict(combo_base),
            ),
            "combo_02": TemplateDefinition(
                template_id="combo_02",
                label="日K组合策略-2",
                strategy_type="combo",
                script_glob="02*.dos",
                default_config={**combo_base, "maxPositionLimit": 10},
            ),
            "combo_03": TemplateDefinition(
                template_id="combo_03",
                label="日K组合策略-3",
                strategy_type="combo",
                script_glob="03*.dos",
                default_config={
                    **combo_base,
                    "dailyBuyCountLimit": 4,
                    "maxPositionLimit": 20,
                    "perStockPercent": 0.05,
                },
            ),
            "timing_13": TemplateDefinition(
                template_id="timing_13",
                label="日K个股择时策略",
                strategy_type="timing",
                script_glob="13*.dos",
                default_config={
                    "buyFactors": ["MA", "K线形态"],
                    "buyFactorConditions": ["站上5日线", "十字星"],
                    "buyConditionRelation": "and",
                    "sellFactors": ["BBI"],
                    "sellFactorConditions": ["股价下穿BBI"],
                    "sellConditionRelation": "or",
                    "cash": 10000000.0,
                    "startDate": "2024.01.01",
                    "endDate": "2025.12.31",
                    "stockUniverse": "600519.SH",
                },
            ),
        }

    def _resolve_script_path(self, template_id: str) -> Path:
        if template_id in self._path_cache:
            return self._path_cache[template_id]
        template = self.get_template(template_id)
        matches = sorted(self._script_root.glob(template.script_glob))
        if not matches:
            raise FileNotFoundError(f"Script not found for template {template_id} under {self._script_root}")
        path = matches[0]
        self._path_cache[template_id] = path
        return path

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "template_id": template.template_id,
                "label": template.label,
                "strategy_type": template.strategy_type,
                "default_config": template.default_config,
            }
            for template in self._templates.values()
        ]

    def get_template(self, template_id: str) -> TemplateDefinition:
        if template_id not in self._templates:
            raise KeyError(f"Unknown template_id: {template_id}")
        return self._templates[template_id]

    def load_script(self, template_id: str) -> str:
        path = self._resolve_script_path(template_id)
        return path.read_text(encoding="utf-8")

    def script_filename(self, template_id: str) -> str:
        return self._resolve_script_path(template_id).name

    def get_factor_meta(self) -> dict[str, Any]:
        return {
            "ranges": [
                "沪深A股",
                "上证A股",
                "深证A股",
                "创业板",
                "科创板",
                "上证50",
                "沪深300",
                "中证1000",
                "中证500",
                "股票",
            ],
            "fundamental_factors": [
                {"label": "总市值", "field": "total_mv"},
                {"label": "市盈率", "field": "pe"},
                {"label": "成交额", "field": "amount"},
            ],
            "technical_factors": [
                {"label": "MA", "field": "ma"},
                {"label": "KDJ", "field": "kdj"},
                {"label": "RSI", "field": "rsi"},
                {"label": "MACD", "field": "macd"},
                {"label": "BOLL", "field": "boll"},
                {"label": "BBI", "field": "bbi"},
                {"label": "K线形态", "field": "kline"},
            ],
            "timing_signal_map": {
                "MACD": ["上移", "金叉", "底背离", "多投排列", "低位金叉", "零轴上金叉", "二次金叉", "红二波", "下移", "死叉", "顶背离", "空头排列"],
                "KDJ": ["金叉", "底背离", "多投排列", "超卖", "拐头向上", "低位金叉", "死叉", "顶背离", "空头排列", "超买", "拐头向下"],
                "RSI": ["超卖", "金叉", "上穿30", "拐头向上", "RSI低位金叉", "超买", "死叉", "跌破70", "拐头向下", "RSI高位死叉"],
                "BOLL": ["开口张开", "突破上轨", "突破中轨", "突破下轨", "开口缩小", "跌破上轨", "跌破中轨", "跌破下轨"],
                "BBI": ["股价下穿BBI"],
                "MA": ["站上5日线", "站上10日线", "站上20日线", "站上30日线", "跌破5日线", "跌破10日线", "跌破20日线", "跌破30日线", "5日下穿10日", "5日下穿20日", "5日下穿30日", "3日下穿15日", "空头排列"],
                "K线形态": ["十字星", "光头阳线", "光头阴线"],
            },
        }
