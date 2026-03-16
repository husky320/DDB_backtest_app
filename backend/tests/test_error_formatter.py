from app.services.error_formatter import format_backtest_error


def test_format_backtest_error_for_position_limit():
    info = format_backtest_error("dailyBuyCountLimit cannot exceed maxPositionLimit.")
    assert info["code"] == "config.position_limit"
    assert "单日最大买入数不能超过账户最大持仓数" in info["summary"]


def test_format_backtest_error_for_order_sensitive_signal():
    raw = "The where clause ... should not use any aggregate or order-sensitive function."
    info = format_backtest_error(raw)
    assert info["code"] == "timing.signal_not_pushdown"
    assert "顺序敏感函数" in info["summary"]

