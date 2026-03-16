import pandas as pd

from app.services.result_serializer import ResultSerializer


def test_serializer_extracts_kpis_and_equity():
    serializer = ResultSerializer()
    raw = {
        "returnSummary": pd.DataFrame(
            [
                {
                    "totalReturn": 1.2,
                    "annualReturn": 0.5,
                    "maxDrawdown": 0.2,
                    "sharpeRatio": 1.1,
                    "numTrades": 12,
                }
            ]
        ),
        "dailyTotalPortfolios": pd.DataFrame(
            [
                {"tradeDate": "2023-01-01", "totalPortfolios": 100.0, "benchmarkNetValue": 100.0},
                {"tradeDate": "2023-01-02", "totalPortfolios": 102.0, "benchmarkNetValue": 101.0},
            ]
        ),
        "tradeDetails": pd.DataFrame([{"symbol": "000001.SZ", "direction": 1}]),
    }
    result = serializer.serialize("r1", "combo_01", raw)
    assert result["kpis"]["totalReturn"] == 1.2
    assert len(result["equity"]) == 2
    assert result["degraded"] is False
    assert result["degraded_reasons"] == []
    assert result["equity"][0]["portfolioValue"] == 1.0
    assert result["equity"][1]["portfolioValue"] == 1.02
    assert result["equity"][0]["benchmarkValue"] == 1.0
    assert result["equity"][1]["benchmarkValue"] == 1.01
    assert len(result["trades"]) == 1
    assert result["no_trade"] is False


def test_serializer_marks_degraded_when_using_fallback_equity():
    serializer = ResultSerializer()
    raw = {
        "returnSummary": pd.DataFrame([{"totalReturn": 0.0}]),
        "dailyTotalPortfolios": pd.DataFrame(
            [
                {"tradeDate": "2024-01-01", "benchmarkNetValue": 1.0},
                {"tradeDate": "2024-01-02", "benchmarkNetValue": 1.01},
            ]
        ),
        "tradeDetails": pd.DataFrame([]),
    }
    result = serializer.serialize(
        "r2",
        "combo_01",
        raw,
        warnings=["dailyTotalPortfolios was empty; generated fallback equity curve from benchmark series."],
    )
    assert result["degraded"] is True
    assert "fallback_equity_curve" in result["degraded_reasons"]
    assert result["no_trade"] is True
    assert "no_trade_records" in result["degraded_reasons"]
    assert result["no_trade_reason"]


def test_serializer_exposes_applied_config():
    serializer = ResultSerializer()
    raw = {
        "returnSummary": pd.DataFrame([{"totalReturn": 0.0, "numTrades": 0}]),
        "dailyTotalPortfolios": pd.DataFrame([{"tradeDate": "2024-01-01", "totalPortfolios": 100.0}]),
        "tradeDetails": pd.DataFrame([]),
    }

    result = serializer.serialize(
        "r3",
        "combo_01",
        raw,
        applied_config={"benchmark": "000002.SZ", "holdingPeriod": 20},
    )

    assert result["applied_config"]["benchmark"] == "000002.SZ"
    assert result["degraded"] is True
    assert result["no_trade"] is True
