import pandas as pd
import pytest

from app.services.backtest_runner import BacktestRunner
from app.services.result_serializer import ResultSerializer
from app.services.script_registry import TemplateDefinition


class _FakeConnection:
    def execute(self, script: str, require_data_node: bool = True):
        if "schema(loadTable" in script:
            return [
                "total_mv",
                "pe",
                "amount",
                "close",
                "ma5",
                "macdDeadCross",
                "pct_chg",
            ]
        if "minute_singal" in script and "count(*)" in script:
            return 100
        return None


class _DummyRegistry:
    def __init__(self, timing_signal_map=None):
        self._timing_signal_map = timing_signal_map or {}

    def get_factor_meta(self):
        return {"timing_signal_map": self._timing_signal_map}


class _FakeSession:
    def __init__(self):
        self.closed = False

    def run(self, script: str):
        if "schema(loadTable" in script:
            return [
                "total_mv",
                "pe",
                "amount",
                "close",
                "ma5",
                "macdDeadCross",
                "pct_chg",
            ]
        if "minute_singal" in script and "count(*)" in script:
            return 100
        if "select top 1 * from loadTable(\"dfs://dailyReturn\"" in script:
            return 1
        if "strategyBackTest" in script:
            return {
                "returnSummary": pd.DataFrame(
                    [
                        {
                            "totalReturn": 0.1,
                            "annualReturn": 0.05,
                            "maxDrawdown": 0.02,
                        }
                    ]
                ),
                "dailyTotalPortfolios": pd.DataFrame(
                    [
                        {"tradeDate": "2024-01-02", "totalPortfolios": 1_000_000, "benchmarkNetValue": 1.0},
                        {"tradeDate": "2024-01-03", "totalPortfolios": 1_010_000, "benchmarkNetValue": 1.01},
                    ]
                ),
                "tradeDetails": pd.DataFrame([]),
            }
        return None

    def close(self):
        self.closed = True


class _FakeTaskConnection:
    def open_task_session(self, require_data_node=True, force_probe=False):
        return _FakeSession()


class _ComboRegistry(_DummyRegistry):
    def get_template(self, template_id: str):
        return TemplateDefinition(
            template_id=template_id,
            label="组合策略",
            strategy_type="combo",
            script_glob="01*.dos",
            default_config=_base_config(),
        )

    def load_script(self, template_id: str) -> str:
        if template_id != "combo_01":
            raise AssertionError(f"unexpected template load: {template_id}")
        return "// framework combo_01"

    def script_filename(self, template_id: str) -> str:
        return "01.combo_01.dos"


def _base_config():
    return {
        "buyFactors": ["total_mv", "pe", "amount", "close", "ma5"],
        "buyFactorConditions": "pe < 80",
        "sellFactors": ["macdDeadCross"],
        "sellFactorConditions": "macdDeadCross == 1",
        "buyPriority": ["pct_chg"],
        "sellPriority": [],
        "cash": 1_000_000,
        "startDate": "2023.01.01",
        "endDate": "2023.12.31",
        "benchmark": "000002.SZ",
        "maxPositionLimit": 5,
        "dailyBuyCountLimit": 2,
    }


def test_validate_combo_rejects_invalid_position_limits():
    runner = BacktestRunner(_FakeConnection(), _DummyRegistry(), ResultSerializer())
    cfg = _base_config()
    cfg["dailyBuyCountLimit"] = 8
    with pytest.raises(ValueError):
        runner._validate_combo_config(cfg, auto_fallback_benchmark=True)


def test_validate_combo_rejects_missing_factor_columns():
    runner = BacktestRunner(_FakeConnection(), _DummyRegistry(), ResultSerializer())
    cfg = _base_config()
    cfg["buyFactors"] = ["unknown_factor"]
    with pytest.raises(ValueError):
        runner._validate_combo_config(cfg, auto_fallback_benchmark=True)


def test_apply_factor_customization_builds_buy_conditions():
    runner = BacktestRunner(_FakeConnection(), _DummyRegistry(), ResultSerializer())
    cfg = _base_config()
    cfg["factorCustomization"] = {
        "buy": {
            "logic": "and",
            "fundamentals": [
                {"field": "pe", "op": "<=", "value": 50, "enabled": True},
                {"field": "total_mv", "op": "<=", "value": 9000000, "enabled": True},
            ],
            "technicals": [
                {"type": "ma_above", "period": 5, "enabled": True},
                {"type": "macd_dead", "enabled": False},
            ],
        },
        "sell": {
            "logic": "or",
            "fundamentals": [],
            "technicals": [{"type": "macd_dead", "enabled": True}],
        },
    }
    day_cols = {"pe", "total_mv", "close", "ma5", "macdDeadCross"}
    warnings, factor_code = runner._apply_factor_customization(cfg, day_cols)
    assert warnings == []
    assert "pe <= 50" in cfg["buyFactorConditions"]
    assert "total_mv <= 9000000" in cfg["buyFactorConditions"]
    assert "close > ma5" in cfg["buyFactorConditions"]
    assert "buyFactors" in cfg and "ma5" in cfg["buyFactors"]
    assert cfg["sellFactorConditions"] == "macdDeadCross == 1"
    assert "macdDeadCross" in cfg["sellFactors"]
    assert factor_code == ""


def _timing_config():
    return {
        "buyFactors": ["MACD"],
        "buyFactorConditions": ["金叉"],
        "sellFactors": ["BBI"],
        "sellFactorConditions": ["股价下穿BBI"],
        "cash": 1_000_000,
        "startDate": "2024.01.01",
        "endDate": "2024.12.31",
    }


def test_timing_alignment_uses_safe_default_signal():
    registry = _DummyRegistry(
        timing_signal_map={
            "MACD": ["上移", "金叉", "下移"],
            "BBI": ["股价下穿BBI"],
        }
    )
    runner = BacktestRunner(_FakeConnection(), registry, ResultSerializer())
    cfg = _timing_config()
    cfg["buyFactorConditions"] = []
    warnings = runner._ensure_timing_signal_alignment(cfg)
    assert cfg["buyFactorConditions"][0] == "金叉"
    assert any("auto-filled defaults" in item for item in warnings)


def test_validate_timing_rejects_unsupported_indicator():
    registry = _DummyRegistry(
        timing_signal_map={
            "MACD": ["上移", "金叉", "下移"],
            "BBI": ["股价下穿BBI"],
        }
    )
    runner = BacktestRunner(_FakeConnection(), registry, ResultSerializer())
    cfg = _timing_config()
    cfg["buyFactorConditions"] = ["金叉"]
    with pytest.raises(ValueError, match="Indicator 'MACD' is currently unsupported in distributed timing engine"):
        runner._validate_timing_config(cfg)


def test_run_uses_current_template_script_for_code_display():
    runner = BacktestRunner(_FakeTaskConnection(), _ComboRegistry(), ResultSerializer())

    result = runner.run(run_id="r1", template_id="combo_01", user_config={})

    code_files = result["code_files"]
    assert code_files[2]["name"] == "02_01.combo_01.dos"
    assert code_files[2]["content"].strip() == "// framework combo_01"
