import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { deleteBacktest, fetchBacktests, fetchRun, fetchTemplates } from "../api/client";
import { useAppState } from "../state/AppStateContext";
import type { BacktestResult, BacktestTaskDetail, BacktestTaskSummary, TemplateMeta } from "../types";

function metric(value: unknown): string {
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(4) : "-";
  if (value === null || value === undefined) return "-";
  return String(value);
}

function metricPercent(value: unknown): string {
  if (typeof value === "number") return Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "-";
  if (value === null || value === undefined) return "-";
  return String(value);
}

function datetimeLabel(raw: string | undefined | null): string {
  if (!raw) return "-";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString("zh-CN", { hour12: false });
}

function statusText(status: string): string {
  if (status === "completed") return "已完成";
  if (status === "degraded") return "已完成（降级）";
  if (status === "failed") return "失败";
  return "运行中";
}

function statusClass(status: string): string {
  if (status === "completed") return "status-badge done";
  if (status === "degraded") return "status-badge degraded";
  if (status === "failed") return "status-badge fail";
  return "status-badge running";
}

function degradedReasonLabel(reason: string): string {
  const mapping: Record<string, string> = {
    fallback_equity_curve: "使用了基准回退净值曲线",
    empty_equity_table: "未返回有效净值主表",
    no_trade_with_fallback_equity: "无交易且使用回退净值",
  };
  return mapping[reason] || reason;
}

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (isRecord(value)) return Object.keys(value).length > 0;
  return true;
}

function formatSimpleValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function renderConfigValue(value: unknown): React.ReactNode {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="muted">-</span>;
    return (
      <div className="snapshot-chip-list">
        {value.map((item, idx) => (
          <span key={`${idx}-${String(item)}`} className="snapshot-chip">
            {formatSimpleValue(item)}
          </span>
        ))}
      </div>
    );
  }
  if (isRecord(value)) {
    return <span className="snapshot-value-mono">{JSON.stringify(value, null, 2)}</span>;
  }
  return <span>{formatSimpleValue(value)}</span>;
}

async function copyTextToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

interface SnapshotField {
  key: string;
  label: string;
}

function SnapshotGroup({ title, config, fields }: { title: string; config: UnknownRecord; fields: SnapshotField[] }) {
  const rows = fields
    .map((field) => ({ ...field, value: config[field.key] }))
    .filter((item) => hasMeaningfulValue(item.value));

  if (rows.length === 0) return null;

  return (
    <section className="snapshot-group">
      <h4>{title}</h4>
      <div className="snapshot-grid">
        {rows.map((item) => (
          <div key={item.key} className="snapshot-item">
            <span className="snapshot-label">{item.label}</span>
            <div className="snapshot-value">{renderConfigValue(item.value)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RequestSnapshot({
  detail,
  templateDefaults,
}: {
  detail: BacktestTaskDetail;
  templateDefaults: Record<string, UnknownRecord>;
}) {
  const request = isRecord(detail.request) ? detail.request : {};
  const userConfig = isRecord(request.user_config) ? request.user_config : {};
  const aiPatch = isRecord(request.ai_patch) ? request.ai_patch : null;
  const templateFromRequest = typeof request.template_id === "string" ? request.template_id : detail.template_id;
  const autoFallback =
    typeof request.auto_fallback_benchmark === "boolean" ? request.auto_fallback_benchmark : undefined;
  const defaultConfig = templateDefaults[String(templateFromRequest)] || {};
  const effectiveConfig: UnknownRecord = { ...defaultConfig, ...userConfig };
  const hasUserOverrides = Object.keys(userConfig).length > 0;

  const basicFields: SnapshotField[] = [
    { key: "startDate", label: "开始日期" },
    { key: "endDate", label: "结束日期" },
    { key: "benchmark", label: "基准" },
    { key: "stockUniverse", label: "股票/范围" },
    { key: "cash", label: "初始资金" },
    { key: "holdingPeriod", label: "持股周期" },
    { key: "maxPositionLimit", label: "最大持仓数" },
    { key: "dailyBuyCountLimit", label: "单日最大买入" },
    { key: "dailySellCountLimit", label: "单日最大卖出" },
    { key: "perStockPercent", label: "单票仓位比例" },
    { key: "industryNumRestrictions", label: "行业持仓上限" },
  ];

  const executionFields: SnapshotField[] = [
    { key: "buyTimeType", label: "买入时间类型" },
    { key: "buyTime", label: "买入时间" },
    { key: "sellTimeType", label: "卖出时间类型" },
    { key: "sellTime", label: "卖出时间" },
    { key: "buyPriority", label: "买入优先级" },
    { key: "buyPriorityFactorsDiretion", label: "买入优先级方向" },
    { key: "sellPriority", label: "卖出优先级" },
    { key: "sellPriorityFactorsDiretion", label: "卖出优先级方向" },
  ];

  const riskFields: SnapshotField[] = [
    { key: "isTakeProfit", label: "启用止盈" },
    { key: "takeProfitType", label: "止盈类型" },
    { key: "takeProfitValue", label: "止盈阈值" },
    { key: "takeProfitRollback", label: "止盈回撤" },
    { key: "isStopLoss", label: "启用止损" },
    { key: "stopLossType", label: "止损类型" },
    { key: "stopLossValue", label: "止损阈值" },
    { key: "stopLossRollback", label: "止损回撤" },
    { key: "stopOrderTimeType", label: "止损止盈触发类型" },
    { key: "stopOrderTiming", label: "止损止盈触发时间" },
  ];

  const factorFields: SnapshotField[] = [
    { key: "buyFactors", label: "买入因子" },
    { key: "buyFactorConditions", label: "买入条件" },
    { key: "buyConditionRelation", label: "买入条件关系" },
    { key: "sellFactors", label: "卖出因子" },
    { key: "sellFactorConditions", label: "卖出条件" },
    { key: "sellConditionRelation", label: "卖出条件关系" },
  ];

  if (!hasMeaningfulValue(effectiveConfig)) {
    return null;
  }

  return (
    <section className="card request-snapshot">
      <details className="snapshot-fold">
        <summary className="snapshot-head">
          <div className="snapshot-head-main">
            <h3>回测配置快照</h3>
            <span className="snapshot-toggle-hint">点击展开</span>
          </div>
          <div className="snapshot-badges">
            <span className="snapshot-badge">模板：{templateFromRequest}</span>
            {autoFallback !== undefined ? (
              <span className="snapshot-badge">{autoFallback ? "基准回退：开启" : "基准回退：关闭"}</span>
            ) : null}
          </div>
        </summary>
        <div className="snapshot-body">
          <p className="muted">
            {hasUserOverrides
              ? "以下为提交该任务时的策略因子与回测参数（模板默认 + 用户覆盖），可用于复盘和对比。"
              : "该任务未提交自定义参数，以下展示模板默认配置。"}
          </p>

          <SnapshotGroup title="基础设置" config={effectiveConfig} fields={basicFields} />
          <SnapshotGroup title="因子设置" config={effectiveConfig} fields={factorFields} />
          <SnapshotGroup title="执行设置" config={effectiveConfig} fields={executionFields} />
          <SnapshotGroup title="风控设置" config={effectiveConfig} fields={riskFields} />

          {aiPatch ? (
            <details className="snapshot-details">
              <summary>查看 AI 补丁（ai_patch）</summary>
              <pre>{JSON.stringify(aiPatch, null, 2)}</pre>
            </details>
          ) : null}

          <details className="snapshot-details">
            <summary>查看原始回测请求 JSON</summary>
            <pre>{JSON.stringify(request, null, 2)}</pre>
          </details>
        </div>
      </details>
    </section>
  );
}

function buildChartRows(result: BacktestResult) {
  let peak = 0;
  const baseRows = (result.equity || []).map((row) => {
    const portfolioValue = typeof row.portfolioValue === "number" ? row.portfolioValue : null;
    const benchmarkValue = typeof row.benchmarkValue === "number" ? row.benchmarkValue : null;
    if (typeof portfolioValue === "number" && portfolioValue > peak) {
      peak = portfolioValue;
    }
    const drawdownPct = peak > 0 && typeof portfolioValue === "number" ? (portfolioValue - peak) / peak : 0;
    const excessValue =
      typeof portfolioValue === "number" && typeof benchmarkValue === "number" ? portfolioValue - benchmarkValue : null;
    return {
      ...row,
      excessValue,
      drawdownPct,
    };
  });

  const closes = baseRows.map((row) => row.portfolioValue);
  const ma = (period: number) =>
    closes.map((_, index) => {
      if (index + 1 < period) return null;
      const window = closes.slice(index + 1 - period, index + 1);
      if (window.some((value) => typeof value !== "number")) return null;
      const values = window as number[];
      return values.reduce((sum, value) => sum + value, 0) / period;
    });

  const ema = (period: number) => {
    const alpha = 2 / (period + 1);
    let previous: number | null = null;
    return closes.map((value) => {
      if (typeof value !== "number") return previous;
      previous = previous === null ? value : alpha * value + (1 - alpha) * previous;
      return previous;
    });
  };

  const ma3 = ma(3);
  const ma5 = ma(5);
  const ma6 = ma(6);
  const ma10 = ma(10);
  const ma12 = ma(12);
  const ma20 = ma(20);
  const ma24 = ma(24);
  const ma30 = ma(30);
  const ema12 = ema(12);
  const ema26 = ema(26);
  const macdDif = closes.map((_, index) =>
    typeof ema12[index] === "number" && typeof ema26[index] === "number" ? (ema12[index] as number) - (ema26[index] as number) : null
  );
  const macdDea = (() => {
    const alpha = 2 / (9 + 1);
    let previous: number | null = null;
    return macdDif.map((value) => {
      if (typeof value !== "number") return previous;
      previous = previous === null ? value : alpha * value + (1 - alpha) * previous;
      return previous;
    });
  })();
  const macdHist = macdDif.map((value, index) =>
    typeof value === "number" && typeof macdDea[index] === "number" ? value - (macdDea[index] as number) : null
  );
  const rsi14 = closes.map((_, index) => {
    if (index < 14) return null;
    let gain = 0;
    let loss = 0;
    for (let i = index - 13; i <= index; i += 1) {
      const current = closes[i];
      const previous = closes[i - 1];
      if (typeof current !== "number" || typeof previous !== "number") return null;
      const diff = current - previous;
      if (diff >= 0) gain += diff;
      else loss += Math.abs(diff);
    }
    if (loss === 0) return 100;
    const rs = gain / loss;
    return 100 - 100 / (1 + rs);
  });
  const bollMid = ma20;
  const bollStd = closes.map((_, index) => {
    if (index + 1 < 20) return null;
    const window = closes.slice(index + 1 - 20, index + 1);
    if (window.some((value) => typeof value !== "number")) return null;
    const values = window as number[];
    const avg = values.reduce((sum, value) => sum + value, 0) / 20;
    const variance = values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / 20;
    return Math.sqrt(variance);
  });
  const bollUpper = bollMid.map((value, index) =>
    typeof value === "number" && typeof bollStd[index] === "number" ? value + 2 * (bollStd[index] as number) : null
  );
  const bollLower = bollMid.map((value, index) =>
    typeof value === "number" && typeof bollStd[index] === "number" ? value - 2 * (bollStd[index] as number) : null
  );
  const bbi = closes.map((_, index) => {
    const values = [ma3[index], ma6[index], ma12[index], ma24[index]];
    if (values.some((value) => typeof value !== "number")) return null;
    return (values as number[]).reduce((sum, value) => sum + value, 0) / 4;
  });
  const kdj = (() => {
    let prevK = 50;
    let prevD = 50;
    return closes.map((close, index) => {
      if (index + 1 < 9 || typeof close !== "number") return { k: null, d: null, j: null };
      const window = closes.slice(index + 1 - 9, index + 1).filter((value): value is number => typeof value === "number");
      if (window.length < 9) return { k: null, d: null, j: null };
      const low = Math.min(...window);
      const high = Math.max(...window);
      const rsv = high === low ? 50 : ((close - low) / (high - low)) * 100;
      prevK = (2 * prevK + rsv) / 3;
      prevD = (2 * prevD + prevK) / 3;
      return { k: prevK, d: prevD, j: 3 * prevK - 2 * prevD };
    });
  })();

  return baseRows.map((row, index) => ({
    ...row,
    ma5: ma5[index],
    ma10: ma10[index],
    ma20: ma20[index],
    ma30: ma30[index],
    bollUpper: bollUpper[index],
    bollMid: bollMid[index],
    bollLower: bollLower[index],
    bbi: bbi[index],
    macdDif: macdDif[index],
    macdDea: macdDea[index],
    macdHist: macdHist[index],
    rsi14: rsi14[index],
    kValue: kdj[index].k,
    dValue: kdj[index].d,
    jValue: kdj[index].j,
  }));
}

function chartPercentLabel(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(2)}%`;
}

function buildEffectiveConfig(
  detail: BacktestTaskDetail,
  templateDefaults: Record<string, UnknownRecord>
): UnknownRecord {
  const request = isRecord(detail.request) ? detail.request : {};
  const userConfig = isRecord(request.user_config) ? request.user_config : {};
  const templateFromRequest = typeof request.template_id === "string" ? request.template_id : detail.template_id;
  const defaultConfig = templateDefaults[String(templateFromRequest)] || {};
  return { ...defaultConfig, ...userConfig };
}

function buildStrategyIndicatorTags(config: UnknownRecord): string[] {
  const tags: string[] = [];
  const pushList = (prefix: string, value: unknown) => {
    if (!Array.isArray(value)) return;
    for (const item of value) {
      const text = String(item || "").trim();
      if (text) tags.push(`${prefix}${text}`);
    }
  };

  pushList("买入因子: ", config.buyFactors);
  pushList("卖出因子: ", config.sellFactors);

  const custom = config.factorCustomization;
  if (isRecord(custom)) {
    const sides: Array<{ key: string; prefix: string }> = [
      { key: "buy", prefix: "买入规则: " },
      { key: "sell", prefix: "卖出规则: " },
    ];
    for (const side of sides) {
      const ruleSet = isRecord(custom[side.key]) ? (custom[side.key] as UnknownRecord) : side.key === "buy" ? custom : null;
      if (!ruleSet) continue;
      const fundamentals = Array.isArray(ruleSet.fundamentals) ? ruleSet.fundamentals : [];
      const technicals = Array.isArray(ruleSet.technicals) ? ruleSet.technicals : [];
      for (const item of fundamentals) {
        if (!isRecord(item) || item.enabled === false) continue;
        const label = String(item.label || item.field || "").trim();
        if (label) tags.push(`${side.prefix}${label}`);
      }
      for (const item of technicals) {
        if (!isRecord(item) || item.enabled === false) continue;
        const label = String(item.label || item.type || "").trim();
        if (label) tags.push(`${side.prefix}${label}`);
      }
    }
  }

  return Array.from(new Set(tags));
}

interface VisualIndicatorOption {
  key: string;
  label: string;
  placement: "overlay" | "subplot";
}

function buildVisualIndicatorOptions(tags: string[]): { visual: VisualIndicatorOption[]; staticTags: string[] } {
  const visualMap = new Map<string, VisualIndicatorOption>();
  const staticTags: string[] = [];
  const addVisual = (key: string, label: string, placement: "overlay" | "subplot") => {
    if (!visualMap.has(key)) {
      visualMap.set(key, { key, label, placement });
    }
  };

  for (const tag of tags) {
    const text = String(tag);
    if (/MA5|5日线/.test(text)) {
      addVisual("ma5", "MA5", "overlay");
      continue;
    }
    if (/MA10|10日线/.test(text)) {
      addVisual("ma10", "MA10", "overlay");
      continue;
    }
    if (/MA20|20日线/.test(text)) {
      addVisual("ma20", "MA20", "overlay");
      continue;
    }
    if (/MA30|30日线/.test(text)) {
      addVisual("ma30", "MA30", "overlay");
      continue;
    }
    if (/MACD/.test(text)) {
      addVisual("macd", "MACD", "subplot");
      continue;
    }
    if (/RSI/.test(text)) {
      addVisual("rsi", "RSI", "subplot");
      continue;
    }
    if (/KDJ/.test(text)) {
      addVisual("kdj", "KDJ", "subplot");
      continue;
    }
    if (/BOLL|布林/.test(text)) {
      addVisual("boll", "BOLL", "overlay");
      continue;
    }
    if (/BBI/.test(text)) {
      addVisual("bbi", "BBI", "overlay");
      continue;
    }
    staticTags.push(text);
  }

  return { visual: Array.from(visualMap.values()), staticTags: Array.from(new Set(staticTags)) };
}

function ResultDetail({
  result,
  templateId,
  detail,
  templateDefaults,
}: {
  result: BacktestResult;
  templateId: string;
  detail: BacktestTaskDetail;
  templateDefaults: Record<string, UnknownRecord>;
}) {
  const kpis = result.kpis || {};
  const chartRows = buildChartRows(result);
  const effectiveConfig = buildEffectiveConfig(detail, templateDefaults);
  const strategyIndicatorTags = useMemo(() => buildStrategyIndicatorTags(effectiveConfig), [effectiveConfig]);
  const { visual: visualIndicatorOptions, staticTags: staticStrategyTags } = useMemo(
    () => buildVisualIndicatorOptions(strategyIndicatorTags),
    [strategyIndicatorTags]
  );
  const codeFiles = result.code_files || [];
  const factorCode = codeFiles.find((item) => item.kind === "factor_processing");
  const runCode = codeFiles.find((item) => item.kind === "backtest_run");
  const frameworkCode = codeFiles.find((item) => item.kind === "framework_02");

  const [tradePage, setTradePage] = useState(1);
  const [copiedCodeKey, setCopiedCodeKey] = useState("");
  const [visibleSeries, setVisibleSeries] = useState<Record<string, boolean>>({
    portfolioValue: true,
    benchmarkValue: true,
    excessValue: true,
    drawdownPct: true,
  });
  const [selectedIndicators, setSelectedIndicators] = useState<Record<string, boolean>>({});
  const pageSize = 20;
  const tradeRows = result.trades || [];
  const totalPages = Math.max(1, Math.ceil(tradeRows.length / pageSize));
  const start = (tradePage - 1) * pageSize;
  const end = Math.min(tradeRows.length, start + pageSize);
  const pageRows = tradeRows.slice(start, end);
  const tradeColumns = pageRows[0] ? Object.keys(pageRows[0]) : tradeRows[0] ? Object.keys(tradeRows[0]) : [];

  useEffect(() => {
    setTradePage(1);
    setCopiedCodeKey("");
    setVisibleSeries({
      portfolioValue: true,
      benchmarkValue: true,
      excessValue: true,
      drawdownPct: true,
    });
    setSelectedIndicators({});
  }, [result.run_id]);

  const codeCards = [
    {
      key: "code-00",
      name: factorCode?.name || "00_factor_processing.dos",
      included: Boolean(factorCode?.included),
      content: factorCode?.included ? factorCode.content : "// 当前策略未引入额外因子计算代码。",
    },
    {
      key: "code-01",
      name: runCode?.name || "01_backtest_run.dos",
      included: true,
      content: runCode?.content || "// 未获取到执行脚本。",
    },
    {
      key: "code-02",
      name: frameworkCode?.name || "02_backtest_framework_template_02.dos",
      included: true,
      content: frameworkCode?.content || "// 未获取到模板 02 的框架代码。",
    },
  ];

  const handleCopyCode = async (key: string, content: string) => {
    try {
      await copyTextToClipboard(content);
      setCopiedCodeKey(key);
      window.setTimeout(() => setCopiedCodeKey((prev) => (prev === key ? "" : prev)), 1500);
    } catch {
      setCopiedCodeKey("");
    }
  };

  const chartSeriesOptions = [
    { key: "portfolioValue", label: "策略净值" },
    { key: "benchmarkValue", label: "基准净值" },
    { key: "excessValue", label: "超额收益线" },
    { key: "drawdownPct", label: "回撤曲线" },
  ];

  return (
    <div className="page-stack">
      <section className="card">
        <h3>{detail.strategy_label || "任务结果总览"}</h3>
        <p className="muted">模板：{templateId}</p>
        <p className="muted">创建时间：{datetimeLabel(detail.created_at || result.execution?.started_at)}</p>
        {result.degraded ? (
          <div className="degraded-box">
            <strong>降级完成：</strong>
            <span>
              {(result.degraded_reasons || []).length > 0
                ? (result.degraded_reasons || []).map((item) => degradedReasonLabel(item)).join("；")
                : "结果可用但存在数据完整性风险"}
            </span>
          </div>
        ) : null}
      </section>

      <section className="card stats-grid">
        <div className="stat">
          <span>总收益率(%)</span>
          <strong>{metricPercent(kpis.totalReturn)}</strong>
        </div>
        <div className="stat">
          <span>年化收益率(%)</span>
          <strong>{metricPercent(kpis.annualReturn)}</strong>
        </div>
        <div className="stat">
          <span>最大回撤率(%)</span>
          <strong>{metricPercent(kpis.maxDrawdown)}</strong>
        </div>
        <div className="stat">
          <span>夏普比率</span>
          <strong>{metric(kpis.sharpeRatio)}</strong>
        </div>
        <div className="stat">
          <span>交易次数</span>
          <strong>{metric(kpis.numTrades)}</strong>
        </div>
        <div className="stat">
          <span>胜率(%)</span>
          <strong>{metricPercent(kpis.winRate)}</strong>
        </div>
        <div className="stat">
          <span>换手率(%)</span>
          <strong>{metricPercent(kpis.turnoverRate)}</strong>
        </div>
        <div className="stat">
          <span>期末权益</span>
          <strong>{metric(kpis.totalEquity)}</strong>
        </div>
      </section>

      <section className="card chart-card">
        <div className="chart-card-head">
          <div>
            <h3>净值与回撤</h3>
            <p className="muted">净值、基准、超额和回撤共用同一时间轴，你可以勾选需要展示的指标。</p>
          </div>
          <div className="chart-tags">
            <span className="snapshot-chip">模板：{templateId}</span>
            <span className="snapshot-chip">任务 ID：{result.run_id.slice(0, 8)}</span>
          </div>
        </div>
        <div className="chart-control-panel">
          <div className="chart-selector-group">
            <span className="chart-selector-title">图表指标</span>
            <div className="chart-button-grid">
              {chartSeriesOptions.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={visibleSeries[item.key] ? "chart-toggle-btn active" : "chart-toggle-btn"}
                  onClick={() => setVisibleSeries((prev) => ({ ...prev, [item.key]: !prev[item.key] }))}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          {visualIndicatorOptions.length > 0 ? (
            <div className="chart-selector-group">
              <span className="chart-selector-title">策略相关指标</span>
              <div className="chart-button-grid chart-button-grid-wide">
                {visualIndicatorOptions.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    className={selectedIndicators[item.key] ? "chart-toggle-btn active" : "chart-toggle-btn"}
                    onClick={() => setSelectedIndicators((prev) => ({ ...prev, [item.key]: !prev[item.key] }))}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {staticStrategyTags.length > 0 ? (
            <div className="chart-selector-group">
              <span className="chart-selector-title">筛选因子</span>
              <div className="snapshot-chip-list">
                {staticStrategyTags.map((item) => (
                  <span key={item} className="snapshot-chip">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="chart-stack">
          <div className="chart-wrap chart-wrap-lg">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartRows} syncId={`task-chart-${result.run_id}`}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="tradeDate" tick={false} axisLine={false} height={18} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                {visibleSeries.portfolioValue ? (
                  <Line type="monotone" dataKey="portfolioValue" name="策略净值" stroke="#03d5ff" dot={false} />
                ) : null}
                {visibleSeries.benchmarkValue ? (
                  <Line type="monotone" dataKey="benchmarkValue" name="基准净值" stroke="#8a99b4" dot={false} />
                ) : null}
                {visibleSeries.excessValue ? (
                  <Line type="monotone" dataKey="excessValue" name="超额收益线" stroke="#35f2a1" dot={false} />
                ) : null}
                {selectedIndicators.ma5 ? <Line type="monotone" dataKey="ma5" name="MA5" stroke="#ffd166" dot={false} /> : null}
                {selectedIndicators.ma10 ? <Line type="monotone" dataKey="ma10" name="MA10" stroke="#ff9f1c" dot={false} /> : null}
                {selectedIndicators.ma20 ? <Line type="monotone" dataKey="ma20" name="MA20" stroke="#ff6b6b" dot={false} /> : null}
                {selectedIndicators.ma30 ? <Line type="monotone" dataKey="ma30" name="MA30" stroke="#c77dff" dot={false} /> : null}
                {selectedIndicators.boll ? <Line type="monotone" dataKey="bollUpper" name="BOLL上轨" stroke="#9ad1ff" dot={false} /> : null}
                {selectedIndicators.boll ? <Line type="monotone" dataKey="bollMid" name="BOLL中轨" stroke="#7bdff2" dot={false} /> : null}
                {selectedIndicators.boll ? <Line type="monotone" dataKey="bollLower" name="BOLL下轨" stroke="#9ad1ff" dot={false} /> : null}
                {selectedIndicators.bbi ? <Line type="monotone" dataKey="bbi" name="BBI" stroke="#86efac" dot={false} /> : null}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {visibleSeries.drawdownPct ? (
            <div className="chart-wrap chart-wrap-sm chart-subplot">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartRows} syncId={`task-chart-${result.run_id}`}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tradeDate" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} />
                  <Tooltip formatter={(value) => chartPercentLabel(value)} />
                  <Area type="monotone" dataKey="drawdownPct" name="回撤曲线" stroke="#ff7c9a" fill="rgba(255,91,127,0.26)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          {selectedIndicators.macd ? (
            <div className="chart-wrap chart-wrap-sm chart-subplot">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartRows} syncId={`task-chart-${result.run_id}`}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tradeDate" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="macdDif" name="DIF" stroke="#ffd166" dot={false} />
                  <Line type="monotone" dataKey="macdDea" name="DEA" stroke="#7bdff2" dot={false} />
                  <Line type="monotone" dataKey="macdHist" name="MACD" stroke="#ff7c9a" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          {selectedIndicators.rsi ? (
            <div className="chart-wrap chart-wrap-sm chart-subplot">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartRows} syncId={`task-chart-${result.run_id}`}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tradeDate" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="rsi14" name="RSI(14)" stroke="#9bffb0" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          {selectedIndicators.kdj ? (
            <div className="chart-wrap chart-wrap-sm chart-subplot">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartRows} syncId={`task-chart-${result.run_id}`}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="tradeDate" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="kValue" name="K" stroke="#ffd166" dot={false} />
                  <Line type="monotone" dataKey="dValue" name="D" stroke="#7bdff2" dot={false} />
                  <Line type="monotone" dataKey="jValue" name="J" stroke="#ff7c9a" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </div>
      </section>

      <RequestSnapshot detail={detail} templateDefaults={templateDefaults} />

      <section className="card">
        <h3>任务执行信息</h3>
        <div className="execution-grid">
          <div>
            <span className="muted">开始时间：</span>
            <span>{datetimeLabel(result.execution?.started_at)}</span>
          </div>
          <div>
            <span className="muted">结束时间：</span>
            <span>{datetimeLabel(result.execution?.finished_at)}</span>
          </div>
          <div>
            <span className="muted">运行时长：</span>
            <span>{typeof result.execution?.duration_ms === "number" ? `${result.execution.duration_ms} ms` : "-"}</span>
          </div>
          <div>
            <span className="muted">告警数：</span>
            <span>{result.warnings.length}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>提交到 DolphinDB 的代码</h3>
        <div className="code-file-grid">
          {codeCards.map((card) => (
            <details key={card.key} className="code-file code-fold">
              <summary className="code-file-head">
                <div className="code-head-main">
                  <strong>{card.name}</strong>
                  <span className={card.included ? "tag-on" : "tag-off"}>{card.included ? "已包含" : "未生成"}</span>
                </div>
                <button
                  type="button"
                  className="code-copy-btn"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleCopyCode(card.key, card.content);
                  }}
                >
                  {copiedCodeKey === card.key ? "已复制" : "复制代码"}
                </button>
              </summary>
              <pre>{card.content}</pre>
            </details>
          ))}
        </div>
      </section>

      <section className="card">
        <details className="result-details">
          <summary>历史交易明细（仅当前任务）</summary>
          <p className="muted">
            共 {tradeRows.length} 条，当前第 {tradePage}/{totalPages} 页
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {tradeColumns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, idx) => (
                  <tr key={idx}>
                    {tradeColumns.map((col) => (
                      <td key={col}>{String((row as Record<string, unknown>)[col] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button type="button" onClick={() => setTradePage((p) => Math.max(1, p - 1))} disabled={tradePage <= 1}>
              上一页
            </button>
            <button
              type="button"
              onClick={() => setTradePage((p) => Math.min(totalPages, p + 1))}
              disabled={tradePage >= totalPages}
            >
              下一页
            </button>
          </div>
        </details>
      </section>
    </div>
  );
}

export function AnalysisPage() {
  const { setLastResult } = useAppState();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasks, setTasks] = useState<BacktestTaskSummary[]>([]);
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [detail, setDetail] = useState<BacktestTaskDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [deletingRunId, setDeletingRunId] = useState("");
  const selectedRunId = searchParams.get("run_id");

  useEffect(() => {
    let cancelled = false;
    const loadList = async () => {
      try {
        const items = await fetchBacktests(300);
        if (cancelled) return;
        setTasks(items);
        if ((!selectedRunId || !items.some((item) => item.run_id === selectedRunId)) && items.length > 0) {
          setSearchParams({ run_id: items[0].run_id }, { replace: true });
        } else if (items.length === 0 && selectedRunId) {
          setSearchParams({}, { replace: true });
        }
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    };
    loadList().catch(() => undefined);
    const timer = window.setInterval(() => {
      loadList().catch(() => undefined);
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedRunId, setSearchParams]);

  useEffect(() => {
    let cancelled = false;
    const loadTemplates = async () => {
      const items = await fetchTemplates();
      if (!cancelled) {
        setTemplates(items);
      }
    };
    loadTemplates().catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    const loadDetail = async () => {
      setLoadingDetail(true);
      try {
        const item = await fetchRun(selectedRunId);
        if (cancelled) return;
        setDetail(item);
        if ((item.status === "completed" || item.status === "degraded") && item.result) {
          setLastResult(item.result);
        }
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    };
    loadDetail().catch(() => undefined);
    const timer = window.setInterval(() => {
      loadDetail().catch(() => undefined);
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedRunId, setLastResult]);

  const selectedSummary = useMemo(
    () => tasks.find((item) => item.run_id === selectedRunId) || null,
    [tasks, selectedRunId]
  );
  const templateDefaults = useMemo<Record<string, UnknownRecord>>(() => {
    const map: Record<string, UnknownRecord> = {};
    for (const item of templates) {
      if (isRecord(item.default_config)) {
        map[item.template_id] = item.default_config;
      }
    }
    return map;
  }, [templates]);

  const handleDeleteTask = async (runId: string) => {
    const target = tasks.find((item) => item.run_id === runId);
    const title = target?.strategy_label || runId;
    if (!window.confirm(`确认删除任务“${title}”？删除后将不再参与 AI 推荐策略汇总。`)) {
      return;
    }
    setDeletingRunId(runId);
    try {
      await deleteBacktest(runId);
      const remaining = tasks.filter((item) => item.run_id !== runId);
      setTasks(remaining);
      if (selectedRunId === runId) {
        setDetail(null);
        const next = remaining[0]?.run_id;
        if (next) {
          setSearchParams({ run_id: next }, { replace: true });
        } else {
          setSearchParams({}, { replace: true });
        }
      }
    } finally {
      setDeletingRunId("");
    }
  };

  return (
    <div className="tasks-layout">
      <section className="card task-list-card">
        <h2>回测任务</h2>
        <p className="muted">按时间查看任务状态，点击左侧条目进入任务详情。</p>
        {loadingList ? <p className="muted">任务列表加载中...</p> : null}
        <div className="task-list">
          {tasks.map((item) => {
            const active = item.run_id === selectedRunId;
            return (
              <div
                key={item.run_id}
                className={active ? "task-item active" : "task-item"}
                role="button"
                tabIndex={0}
                onClick={() => setSearchParams({ run_id: item.run_id })}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSearchParams({ run_id: item.run_id });
                  }
                }}
              >
                <div className="task-item-main">
                  <div className="task-item-top">
                    <strong>{item.strategy_label || item.template_id}</strong>
                    <div className="task-item-actions">
                      <span className={statusClass(item.status)}>{statusText(item.status)}</span>
                      <button
                        type="button"
                        className="task-delete-btn"
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          handleDeleteTask(item.run_id);
                        }}
                        disabled={deletingRunId === item.run_id}
                      >
                        {deletingRunId === item.run_id ? "删除中" : "删除"}
                      </button>
                    </div>
                  </div>
                  <div className="task-item-meta">模板：{item.template_id}</div>
                  <div className="task-item-meta">创建：{datetimeLabel(item.created_at)}</div>
                  <div className="task-item-meta">
                    耗时：{typeof item.duration_ms === "number" ? `${item.duration_ms} ms` : "-"}
                  </div>
                </div>
              </div>
            );
          })}
          {tasks.length === 0 && !loadingList ? <div className="muted">暂无任务，请先到回测页提交任务。</div> : null}
        </div>
      </section>

      <section className="task-detail">
        {!selectedRunId ? (
          <div className="card">请选择一个任务查看详情。</div>
        ) : loadingDetail && !detail ? (
          <div className="card">任务详情加载中...</div>
        ) : (
          <>
            {detail?.status === "failed" ? (
              <div className="card">
                <h3>{detail.strategy_label || detail.error_info?.title || "任务失败"}</h3>
                <p className="muted">模板：{detail.template_id}</p>
                <p className="muted">{detail.error_info?.summary || detail.error || "无错误信息。"}</p>
                {detail.error_info?.suggestion ? <p className="muted">建议：{detail.error_info.suggestion}</p> : null}
                {detail.error_detail ? (
                  <details>
                    <summary>查看原始错误详情</summary>
                    <pre>{detail.error_detail}</pre>
                  </details>
                ) : null}
              </div>
            ) : detail?.status !== "completed" && detail?.status !== "degraded" ? (
              <div className="card">
                <h3>{detail?.strategy_label || selectedSummary?.strategy_label || "任务运行中"}</h3>
                <p className="muted">模板：{detail?.template_id || selectedSummary?.template_id}</p>
                <p className="muted">任务 ID：{selectedRunId}</p>
                <p className="muted">状态：{statusText(detail?.status || selectedSummary?.status || "running")}</p>
                <p className="muted">创建时间：{datetimeLabel(selectedSummary?.created_at)}</p>
              </div>
            ) : detail.result ? (
              <ResultDetail
                result={detail.result}
                templateId={detail.template_id}
                detail={detail}
                templateDefaults={templateDefaults}
              />
            ) : (
              <div className="card">任务已结束，但未返回结果。</div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
