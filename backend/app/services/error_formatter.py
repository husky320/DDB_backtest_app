from __future__ import annotations

import re
from typing import Any


def _clean(text: str) -> str:
    normalized = (text or "").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_first_sentence(text: str, max_len: int = 260) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    for sep in [". ", "。", "; ", "；", " | "]:
        idx = cleaned.find(sep)
        if idx > 0:
            cleaned = cleaned[:idx]
            break
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def format_backtest_error(raw_error: str) -> dict[str, Any]:
    text = str(raw_error or "")
    cleaned = _clean(text)

    if "dailyBuyCountLimit cannot exceed maxPositionLimit" in text:
        return {
            "title": "参数校验失败",
            "summary": "单日最大买入数不能超过账户最大持仓数。",
            "suggestion": "请将 dailyBuyCountLimit 调小，或将 maxPositionLimit 调大。",
            "code": "config.position_limit",
        }

    if "startDate must be earlier than or equal to endDate" in text:
        return {
            "title": "参数校验失败",
            "summary": "开始日期不能晚于结束日期。",
            "suggestion": "请调整回测区间，确保 startDate <= endDate。",
            "code": "config.date_order",
        }

    if "Missing factor fields in day_singal" in text:
        return {
            "title": "因子字段不存在",
            "summary": _extract_first_sentence(text),
            "suggestion": "请检查买卖因子字段是否存在于 day_singal 表结构中。",
            "code": "config.factor_field_missing",
        }

    if "has no minute data in minute_singal" in text:
        return {
            "title": "基准分钟数据缺失",
            "summary": _extract_first_sentence(text),
            "suggestion": "请切换基准，或启用自动回退到可用基准。",
            "code": "config.benchmark_minute_missing",
        }

    if "No available DolphinDB data node for the provided configuration" in text:
        return {
            "title": "连接配置不可用",
            "summary": "保存后的配置无法连通任何可用数据节点，系统已拒绝本次保存。",
            "suggestion": "请检查 Host/Port/账号密码和 candidate_ports 后重试。",
            "code": "config.ddb_connectivity",
        }

    if "order-sensitive function" in text and "where clause" in text:
        return {
            "title": "择时信号不可执行",
            "summary": "当前信号组合触发了分布式查询限制（where 子句包含顺序敏感函数）。",
            "suggestion": "请改用可下推信号组合，避免包含依赖 prev/顺序上下文的条件。",
            "code": "timing.signal_not_pushdown",
        }

    if "Indicator '" in text and "unsupported in distributed timing engine" in text:
        return {
            "title": "择时指标暂不支持",
            "summary": _extract_first_sentence(text),
            "suggestion": "请优先使用 MA、K线形态、BBI 等当前可执行指标。",
            "code": "timing.indicator_unsupported",
        }

    if "Signal '" in text and "unsupported in distributed timing engine" in text:
        return {
            "title": "择时信号暂不支持",
            "summary": _extract_first_sentence(text),
            "suggestion": "请切换到可执行信号，避免顺序敏感表达式。",
            "code": "timing.signal_unsupported",
        }

    if "No supported buy factors remain after timing signal alignment" in text:
        return {
            "title": "买入信号不可执行",
            "summary": "当前买入因子在可执行性校验后不可用。",
            "suggestion": "请至少保留一个支持的买入因子（如 MA 或 K线形态）。",
            "code": "timing.buy_factor_empty",
        }

    return {
        "title": "回测执行失败",
        "summary": _extract_first_sentence(cleaned) or "未知错误",
        "suggestion": "请检查参数配置、数据覆盖范围和 DolphinDB 节点状态后重试。",
        "code": "backtest.unknown",
    }
