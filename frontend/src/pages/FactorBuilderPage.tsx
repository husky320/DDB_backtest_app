import React, { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  analyzeSemanticStrategy,
  fetchBacktests,
  fetchFactorMeta,
  fetchRun,
  recommendStrategyIdeas,
} from "../api/client";
import { ChipGroup } from "../components/ChipGroup";
import { useAppState } from "../state/AppStateContext";
import type {
  BacktestTaskDetail,
  FactorCustomization,
  FactorRuleSet,
  FundamentalCondition,
  SemanticAnalyzeResponse,
  StrategyIdeaResponse,
  TechnicalCondition,
} from "../types";

type Side = "buy" | "sell";
type NumberOp = "<" | "<=" | ">" | ">=" | "==" | "!=";

type FundamentalPreset = {
  label: string;
  op: NumberOp;
  value: number;
};

type TechnicalOption = {
  label: string;
  condition: Omit<TechnicalCondition, "id" | "label" | "enabled">;
};

type ParsedRuleSet = {
  inferredFundamentalLabels: Set<string>;
  inferredTechnicalLabels: Set<string>;
  fundamentalPatches: Record<string, { op: NumberOp; value: number; enabled: boolean }>;
  technicalRules: TechnicalCondition[];
  logic: "and" | "or";
};

type SemanticHints = {
  buy: ParsedRuleSet;
  sell: ParsedRuleSet;
  holdingPeriod?: number;
  benchmark?: string;
};

const DEFAULT_SEMANTIC_TEXT =
  "示例：总市值>20000000，股价站上5日线买入，MACD金叉买入，持有60天，基准设置为万科A。";

const FUNDAMENTAL_PRESETS: Record<string, Record<Side, FundamentalPreset[]>> = {
  pe: {
    buy: [
      { label: "<=10", op: "<=", value: 10 },
      { label: "<=20", op: "<=", value: 20 },
      { label: "<=30", op: "<=", value: 30 },
      { label: "<=50", op: "<=", value: 50 },
    ],
    sell: [
      { label: ">=30", op: ">=", value: 30 },
      { label: ">=50", op: ">=", value: 50 },
      { label: ">=80", op: ">=", value: 80 },
      { label: ">=100", op: ">=", value: 100 },
    ],
  },
  total_mv: {
    buy: [
      { label: ">=2000万", op: ">=", value: 20_000_000 },
      { label: ">=5000万", op: ">=", value: 50_000_000 },
      { label: ">=1亿", op: ">=", value: 100_000_000 },
    ],
    sell: [
      { label: "<=2000万", op: "<=", value: 20_000_000 },
      { label: "<=1000万", op: "<=", value: 10_000_000 },
      { label: ">=20亿", op: ">=", value: 2_000_000_000 },
    ],
  },
  amount: {
    buy: [
      { label: ">=5亿", op: ">=", value: 500_000_000 },
      { label: ">=10亿", op: ">=", value: 1_000_000_000 },
    ],
    sell: [
      { label: "<=3亿", op: "<=", value: 300_000_000 },
      { label: "<=1亿", op: "<=", value: 100_000_000 },
    ],
  },
};

const TECHNICAL_OPTIONS: Record<Side, Record<string, TechnicalOption[]>> = {
  buy: {
    ma: [
      { label: "股价站上 5 日线", condition: { type: "ma_above", period: 5 } },
      { label: "股价站上 10 日线", condition: { type: "ma_above", period: 10 } },
      { label: "股价站上 20 日线", condition: { type: "ma_above", period: 20 } },
      { label: "均线多头排列", condition: { type: "ma_bull_arrangement" } },
    ],
    macd: [{ label: "MACD 金叉", condition: { type: "macd_golden" } }],
    rsi: [{ label: "RSI < 20", condition: { type: "rsi_threshold", op: "<", value: 20 } }],
    kdj: [{ label: "KDJ 金叉", condition: { type: "kdj_golden" } }],
    boll: [{ label: "突破布林上轨", condition: { type: "boll_break_upper" } }],
    bbi: [],
    kline: [],
  },
  sell: {
    ma: [
      { label: "股价跌破 5 日线", condition: { type: "ma_below", period: 5 } },
      { label: "股价跌破 10 日线", condition: { type: "ma_below", period: 10 } },
      { label: "股价跌破 20 日线", condition: { type: "ma_below", period: 20 } },
    ],
    macd: [{ label: "MACD 死叉", condition: { type: "macd_dead" } }],
    rsi: [{ label: "RSI > 70", condition: { type: "rsi_threshold", op: ">", value: 70 } }],
    kdj: [{ label: "KDJ 死叉", condition: { type: "kdj_dead" } }],
    boll: [{ label: "跌破布林下轨", condition: { type: "boll_break_lower" } }],
    bbi: [{ label: "股价下穿 BBI", condition: { type: "bbi_break" } }],
    kline: [],
  },
};

function makeEmptyRuleSet(): FactorRuleSet {
  return { logic: "and", fundamentals: [], technicals: [] };
}

function normalizeRuleSet(raw: unknown): FactorRuleSet {
  if (!raw || typeof raw !== "object") return makeEmptyRuleSet();
  const casted = raw as Partial<FactorRuleSet>;
  return {
    logic: casted.logic === "or" ? "or" : "and",
    fundamentals: Array.isArray(casted.fundamentals) ? casted.fundamentals : [],
    technicals: Array.isArray(casted.technicals) ? casted.technicals : [],
  };
}

function normalizeCustomization(raw: unknown): FactorCustomization {
  if (!raw || typeof raw !== "object") {
    return { buy: makeEmptyRuleSet(), sell: makeEmptyRuleSet() };
  }
  const casted = raw as Partial<FactorCustomization> & Partial<FactorRuleSet>;
  if ("buy" in casted || "sell" in casted) {
    return {
      buy: normalizeRuleSet(casted.buy),
      sell: normalizeRuleSet(casted.sell),
    };
  }
  return {
    buy: normalizeRuleSet(casted),
    sell: makeEmptyRuleSet(),
  };
}

function technicalConditionId(condition: Omit<TechnicalCondition, "id" | "label" | "enabled">): string {
  return [condition.type, condition.period ?? "", condition.op ?? "", condition.value ?? ""].join("__");
}

function dedupeConditions(items: TechnicalCondition[]): TechnicalCondition[] {
  const seen = new Set<string>();
  const output: TechnicalCondition[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    output.push(item);
  }
  return output;
}

function parseNumberWithUnit(raw: string, unitRaw = ""): number {
  const base = Number(raw);
  if (!Number.isFinite(base)) return 0;
  const unit = unitRaw.trim();
  if (unit === "亿") return base * 100_000_000;
  if (unit === "万") return base * 10_000;
  return base;
}

function emptyParsedRuleSet(logic: "and" | "or"): ParsedRuleSet {
  return {
    inferredFundamentalLabels: new Set<string>(),
    inferredTechnicalLabels: new Set<string>(),
    fundamentalPatches: {},
    technicalRules: [],
    logic,
  };
}

function parseSemanticHints(text: string): SemanticHints {
  const logic: "and" | "or" = /(或者|或|任一|任意满足)/.test(text) ? "or" : "and";
  const parsed: SemanticHints = {
    buy: emptyParsedRuleSet(logic),
    sell: emptyParsedRuleSet(logic),
  };
  const clauses = text
    .split(/[，,。；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

  for (const clause of clauses) {
    const side: Side = /(卖出|卖|平仓|止盈|止损)/.test(clause) ? "sell" : "buy";
    const target = parsed[side];

    const peMatch = clause.match(/(?:PE|市盈率)\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)/i);
    if (peMatch) {
      const op = (peMatch[1] === "=" ? "==" : peMatch[1]) as NumberOp;
      target.inferredFundamentalLabels.add("市盈率");
      target.fundamentalPatches.pe = { op, value: Number(peMatch[2]), enabled: true };
    }

    const totalMvMatch = clause.match(/总市值\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)\s*(亿|万)?/);
    if (totalMvMatch) {
      const op = (totalMvMatch[1] === "=" ? "==" : totalMvMatch[1]) as NumberOp;
      target.inferredFundamentalLabels.add("总市值");
      target.fundamentalPatches.total_mv = {
        op,
        value: parseNumberWithUnit(totalMvMatch[2], totalMvMatch[3] || ""),
        enabled: true,
      };
    }

    const amountMatch = clause.match(/成交额\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)\s*(亿|万)?/);
    if (amountMatch) {
      const op = (amountMatch[1] === "=" ? "==" : amountMatch[1]) as NumberOp;
      target.inferredFundamentalLabels.add("成交额");
      target.fundamentalPatches.amount = {
        op,
        value: parseNumberWithUnit(amountMatch[2], amountMatch[3] || ""),
        enabled: true,
      };
    }

    const maAbove = clause.match(/站上\s*(\d+)\s*日线/);
    if (maAbove) {
      const period = Number(maAbove[1]);
      target.inferredTechnicalLabels.add("MA");
      target.technicalRules.push({
        id: technicalConditionId({ type: "ma_above", period }),
        label: `股价站上 ${period} 日线`,
        enabled: true,
        type: "ma_above",
        period,
      });
    }

    const maBelow = clause.match(/(?:跌破|下穿)\s*(\d+)\s*日线/);
    if (maBelow) {
      const period = Number(maBelow[1]);
      target.inferredTechnicalLabels.add("MA");
      target.technicalRules.push({
        id: technicalConditionId({ type: "ma_below", period }),
        label: `股价跌破 ${period} 日线`,
        enabled: true,
        type: "ma_below",
        period,
      });
    }

    if (/MACD/i.test(clause) && /金叉/.test(clause)) {
      target.inferredTechnicalLabels.add("MACD");
      target.technicalRules.push({
        id: technicalConditionId({ type: "macd_golden" }),
        label: "MACD 金叉",
        enabled: true,
        type: "macd_golden",
      });
    }

    if (/MACD/i.test(clause) && /死叉/.test(clause)) {
      target.inferredTechnicalLabels.add("MACD");
      target.technicalRules.push({
        id: technicalConditionId({ type: "macd_dead" }),
        label: "MACD 死叉",
        enabled: true,
        type: "macd_dead",
      });
    }

    if (/KDJ/i.test(clause) && /金叉/.test(clause)) {
      target.inferredTechnicalLabels.add("KDJ");
      target.technicalRules.push({
        id: technicalConditionId({ type: "kdj_golden" }),
        label: "KDJ 金叉",
        enabled: true,
        type: "kdj_golden",
      });
    }

    if (/KDJ/i.test(clause) && /死叉/.test(clause)) {
      target.inferredTechnicalLabels.add("KDJ");
      target.technicalRules.push({
        id: technicalConditionId({ type: "kdj_dead" }),
        label: "KDJ 死叉",
        enabled: true,
        type: "kdj_dead",
      });
    }

    const rsiMatch = clause.match(/RSI\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)/i);
    if (rsiMatch) {
      const op = (rsiMatch[1] === "=" ? "==" : rsiMatch[1]) as NumberOp;
      target.inferredTechnicalLabels.add("RSI");
      target.technicalRules.push({
        id: technicalConditionId({ type: "rsi_threshold", op, value: Number(rsiMatch[2]) }),
        label: `RSI ${op} ${rsiMatch[2]}`,
        enabled: true,
        type: "rsi_threshold",
        op,
        value: Number(rsiMatch[2]),
      });
    }

    if (/(突破|站上).*(BOLL|布林).*上轨/i.test(clause)) {
      target.inferredTechnicalLabels.add("BOLL");
      target.technicalRules.push({
        id: technicalConditionId({ type: "boll_break_upper" }),
        label: "突破布林上轨",
        enabled: true,
        type: "boll_break_upper",
      });
    }

    if (/(跌破|下穿).*(BOLL|布林).*下轨/i.test(clause)) {
      target.inferredTechnicalLabels.add("BOLL");
      target.technicalRules.push({
        id: technicalConditionId({ type: "boll_break_lower" }),
        label: "跌破布林下轨",
        enabled: true,
        type: "boll_break_lower",
      });
    }

    if (/(下穿|跌破)\s*BBI/i.test(clause)) {
      target.inferredTechnicalLabels.add("BBI");
      target.technicalRules.push({
        id: technicalConditionId({ type: "bbi_break" }),
        label: "股价下穿 BBI",
        enabled: true,
        type: "bbi_break",
      });
    }

    const holdMatch = clause.match(/持有\s*(\d+)\s*天/);
    if (holdMatch) {
      parsed.holdingPeriod = Number(holdMatch[1]);
    }

    if (/沪深300|000300/i.test(clause)) {
      parsed.benchmark = "000300.SH";
    }
    if (/万科A|000002/i.test(clause)) {
      parsed.benchmark = "000002.SZ";
    }
  }

  parsed.buy.technicalRules = dedupeConditions(parsed.buy.technicalRules);
  parsed.sell.technicalRules = dedupeConditions(parsed.sell.technicalRules);
  return parsed;
}

function metricPercent(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(2)}%`;
}

function metric(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toFixed(4);
}

function buildFactorCustomizationPatch(next: FactorCustomization): Record<string, unknown> {
  return { factorCustomization: next };
}

export function FactorBuilderPage() {
  const { factorMeta, setFactorMeta, selections, setSelections, config, mergeConfig, templateId } = useAppState();
  const [keyword, setKeyword] = useState("");
  const deferredKeyword = useDeferredValue(keyword.trim().toLowerCase());
  const [semanticText, setSemanticText] = useState(DEFAULT_SEMANTIC_TEXT);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticResult, setSemanticResult] = useState<SemanticAnalyzeResponse | null>(null);
  const [semanticAutoApplied, setSemanticAutoApplied] = useState("");
  const [strategyIdeas, setStrategyIdeas] = useState<StrategyIdeaResponse | null>(null);
  const [ideasLoading, setIdeasLoading] = useState(false);
  const [ideasError, setIdeasError] = useState("");

  useEffect(() => {
    if (factorMeta) return;
    fetchFactorMeta().then(setFactorMeta).catch(() => undefined);
  }, [factorMeta, setFactorMeta]);

  const customization = useMemo(
    () => normalizeCustomization(config.factorCustomization),
    [config.factorCustomization]
  );

  const filteredFundamental = useMemo(() => {
    if (!factorMeta) return [];
    if (!deferredKeyword) return factorMeta.fundamental_factors.map((item) => item.label);
    return factorMeta.fundamental_factors
      .map((item) => item.label)
      .filter((item) => item.toLowerCase().includes(deferredKeyword));
  }, [factorMeta, deferredKeyword]);

  const filteredTechnical = useMemo(() => {
    if (!factorMeta) return [];
    if (!deferredKeyword) return factorMeta.technical_factors.map((item) => item.label);
    return factorMeta.technical_factors
      .map((item) => item.label)
      .filter((item) => item.toLowerCase().includes(deferredKeyword));
  }, [factorMeta, deferredKeyword]);

  const selectedFundamentalDefs = useMemo(() => {
    if (!factorMeta) return [];
    const labelSet = new Set(selections.fundamentals);
    return factorMeta.fundamental_factors.filter((item) => labelSet.has(item.label));
  }, [factorMeta, selections.fundamentals]);

  const selectedTechnicalDefs = useMemo(() => {
    if (!factorMeta) return [];
    const labelSet = new Set(selections.technicals);
    return factorMeta.technical_factors.filter((item) => labelSet.has(item.label));
  }, [factorMeta, selections.technicals]);

  useEffect(() => {
    if (!factorMeta) return;

    const buildFundamentals = (side: Side): FundamentalCondition[] => {
      const byField = new Map(customization[side].fundamentals.map((item) => [item.field, item]));
      return selectedFundamentalDefs.map((item) => {
        const existing = byField.get(item.field);
        if (existing) return existing;
        return {
          id: `${side}-${item.field}`,
          label: item.label,
          field: item.field,
          op: side === "buy" ? ">=" : "<=",
          value: 0,
          enabled: false,
        };
      });
    };

    const buildTechnicals = (side: Side): TechnicalCondition[] => {
      const allowedIds = new Set<string>();
      for (const def of selectedTechnicalDefs) {
        const options = TECHNICAL_OPTIONS[side][def.field] || [];
        for (const option of options) {
          allowedIds.add(technicalConditionId(option.condition));
        }
      }
      return customization[side].technicals.filter((item) => allowedIds.has(item.id));
    };

    const next: FactorCustomization = {
      buy: {
        logic: customization.buy.logic,
        fundamentals: buildFundamentals("buy"),
        technicals: buildTechnicals("buy"),
      },
      sell: {
        logic: customization.sell.logic,
        fundamentals: buildFundamentals("sell"),
        technicals: buildTechnicals("sell"),
      },
    };

    if (JSON.stringify(next) !== JSON.stringify(customization)) {
      mergeConfig(buildFactorCustomizationPatch(next));
    }
  }, [customization, factorMeta, mergeConfig, selectedFundamentalDefs, selectedTechnicalDefs]);

  const updateCustomization = (next: FactorCustomization) => {
    mergeConfig(buildFactorCustomizationPatch(next));
  };

  const updateRuleSet = (side: Side, nextRuleSet: FactorRuleSet) => {
    updateCustomization({
      buy: side === "buy" ? nextRuleSet : customization.buy,
      sell: side === "sell" ? nextRuleSet : customization.sell,
    });
  };

  const updateFundamental = (side: Side, field: string, patch: Partial<FundamentalCondition>) => {
    const next = customization[side].fundamentals.map((item) => (item.field === field ? { ...item, ...patch } : item));
    updateRuleSet(side, { ...customization[side], fundamentals: next });
  };

  const toggleTechnical = (side: Side, label: string, condition: Omit<TechnicalCondition, "id" | "label" | "enabled">) => {
    const id = technicalConditionId(condition);
    const exists = customization[side].technicals.some((item) => item.id === id);
    if (exists) {
      updateRuleSet(side, {
        ...customization[side],
        technicals: customization[side].technicals.filter((item) => item.id !== id),
      });
      return;
    }
    updateRuleSet(side, {
      ...customization[side],
      technicals: dedupeConditions([
        ...customization[side].technicals,
        {
          id,
          label,
          enabled: true,
          ...condition,
        },
      ]),
    });
  };

  const applySemanticFactors = (source?: SemanticAnalyzeResponse, auto = false) => {
    if (!factorMeta) return;
    const semantic = source || semanticResult;
    if (!semantic) return;

    const parsed = parseSemanticHints(semanticText);
    const nextFundamentals = new Set(selections.fundamentals);
    const nextTechnicals = new Set(selections.technicals);
    const fundamentalLabels = new Set(factorMeta.fundamental_factors.map((item) => item.label));
    const technicalLabels = new Set(factorMeta.technical_factors.map((item) => item.label));

    for (const label of semantic.recommended_existing_factors) {
      if (fundamentalLabels.has(label)) nextFundamentals.add(label);
      if (technicalLabels.has(label)) nextTechnicals.add(label);
    }
    for (const side of ["buy", "sell"] as Side[]) {
      for (const label of parsed[side].inferredFundamentalLabels) {
        if (fundamentalLabels.has(label)) nextFundamentals.add(label);
      }
      for (const label of parsed[side].inferredTechnicalLabels) {
        if (technicalLabels.has(label)) nextTechnicals.add(label);
      }
    }

    const selectedFundDefs = factorMeta.fundamental_factors.filter((item) => nextFundamentals.has(item.label));
    const buildSideFundamentals = (side: Side): FundamentalCondition[] => {
      const currentByField = new Map(customization[side].fundamentals.map((item) => [item.field, item]));
      return selectedFundDefs.map((item) => {
        const patch = parsed[side].fundamentalPatches[item.field];
        if (patch) {
          return {
            id: `${side}-${item.field}`,
            label: item.label,
            field: item.field,
            op: patch.op,
            value: patch.value,
            enabled: true,
          };
        }
        const prev = currentByField.get(item.field);
        if (prev) return prev;
        return {
          id: `${side}-${item.field}`,
          label: item.label,
          field: item.field,
          op: side === "buy" ? ">=" : "<=",
          value: 0,
          enabled: false,
        };
      });
    };

    const nextCustomization: FactorCustomization = {
      buy: {
        logic: parsed.buy.logic,
        fundamentals: buildSideFundamentals("buy"),
        technicals: dedupeConditions([...customization.buy.technicals, ...parsed.buy.technicalRules]),
      },
      sell: {
        logic: parsed.sell.logic,
        fundamentals: buildSideFundamentals("sell"),
        technicals: dedupeConditions([...customization.sell.technicals, ...parsed.sell.technicalRules]),
      },
    };

    setSelections((prev) => ({
      ...prev,
      fundamentals: Array.from(nextFundamentals),
      technicals: Array.from(nextTechnicals),
    }));

    const patch: Record<string, unknown> = buildFactorCustomizationPatch(nextCustomization);
    if (typeof parsed.holdingPeriod === "number" && parsed.holdingPeriod > 0) {
      patch.holdingPeriod = parsed.holdingPeriod;
    }
    if (parsed.benchmark) {
      patch.benchmark = parsed.benchmark;
    }
    mergeConfig(patch);

    const buyRuleCount =
      nextCustomization.buy.fundamentals.filter((item) => item.enabled).length + nextCustomization.buy.technicals.length;
    const sellRuleCount =
      nextCustomization.sell.fundamentals.filter((item) => item.enabled).length + nextCustomization.sell.technicals.length;
    const summary = [`买入规则 ${buyRuleCount} 条`];
    if (sellRuleCount > 0) {
      summary.push(`卖出规则 ${sellRuleCount} 条`);
    } else {
      summary.push("未显式设置卖出规则，继续使用模板默认卖出逻辑");
    }
    setSemanticAutoApplied(`${auto ? "已自动勾选并回填条件" : "已应用语义建议"}：${summary.join("，")}。`);
  };

  const runSemantic = async () => {
    if (!semanticText.trim()) return;
    setSemanticLoading(true);
    setSemanticAutoApplied("");
    try {
      const result = await analyzeSemanticStrategy({ strategy_text: semanticText });
      setSemanticResult(result);
      if (result.supported) {
        applySemanticFactors(result, true);
      }
    } catch (error: any) {
      setSemanticResult({
        supported: false,
        framework_supported: false,
        message: error?.response?.data?.detail || "语义分析失败，请检查模型配置。",
        required_new_factors: [],
        recommended_existing_factors: [],
      });
      setSemanticAutoApplied("");
    } finally {
      setSemanticLoading(false);
    }
  };

  const generateStrategyIdeas = async () => {
    setIdeasLoading(true);
    setIdeasError("");
    try {
      const summaries = await fetchBacktests(60);
      const candidateIds = summaries
        .filter((item) => item.status === "completed" || item.status === "degraded")
        .slice(0, 12)
        .map((item) => item.run_id);
      const details = (await Promise.all(candidateIds.map((runId) => fetchRun(runId)))).filter(
        (item): item is BacktestTaskDetail => Boolean(item?.result)
      );
      const response = await recommendStrategyIdeas({
        template_id: templateId,
        selected_ranges: selections.ranges,
        selected_fundamental_factors: selections.fundamentals,
        selected_technical_factors: selections.technicals,
        current_config: config,
        backtest_tasks: details,
      });
      setStrategyIdeas(response);
    } catch (error: any) {
      setIdeasError(error?.response?.data?.detail || "策略推荐生成失败，请稍后重试。");
    } finally {
      setIdeasLoading(false);
    }
  };

  if (!factorMeta) {
    return <div className="card">加载因子元数据中...</div>;
  }

  const renderFundamentalPanel = (side: Side) => {
    const label = side === "buy" ? "买入条件" : "卖出条件";
    const helper =
      side === "buy"
        ? "未启用的基本面规则不会覆盖模板默认买入条件。"
        : "如果这里不设置卖出规则，回测仍按模板默认卖出逻辑执行。";

    return (
      <div className="signal-panel" key={side}>
        <div className="signal-panel-head">
          <h4>{label}</h4>
          <span className="muted">{helper}</span>
        </div>
        <div className="condition-list">
          {selectedFundamentalDefs.length === 0 ? (
            <div className="muted">请先在上方勾选需要参与策略的基本面因子。</div>
          ) : null}
          {selectedFundamentalDefs.map((item) => {
            const cond = customization[side].fundamentals.find((rule) => rule.field === item.field);
            if (!cond) return null;
            return (
              <div key={`${side}-${item.field}`} className="condition-row">
                <label className="toggle-line">
                  <input
                    type="checkbox"
                    checked={cond.enabled}
                    onChange={(event) => updateFundamental(side, item.field, { enabled: event.target.checked })}
                  />
                  <span>{item.label}</span>
                </label>
                <div className="factor-rule-controls">
                  <select value={cond.op} onChange={(event) => updateFundamental(side, item.field, { op: event.target.value as NumberOp })}>
                    <option value="<">&lt;</option>
                    <option value="<=">&lt;=</option>
                    <option value=">">&gt;</option>
                    <option value=">=">&gt;=</option>
                    <option value="==">==</option>
                    <option value="!=">!=</option>
                  </select>
                  <input
                    type="number"
                    value={Number.isFinite(cond.value) ? cond.value : 0}
                    onChange={(event) => updateFundamental(side, item.field, { value: Number(event.target.value) })}
                  />
                </div>
                <div className="preset-wrap">
                  {(FUNDAMENTAL_PRESETS[item.field]?.[side] || []).map((preset) => (
                    <button
                      key={`${side}-${item.field}-${preset.label}`}
                      type="button"
                      className="chip"
                      onClick={() =>
                        updateFundamental(side, item.field, {
                          enabled: true,
                          op: preset.op,
                          value: preset.value,
                        })
                      }
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderTechnicalPanel = (side: Side) => {
    const label = side === "buy" ? "买入信号" : "卖出信号";
    const helper =
      side === "buy"
        ? "技术买点建议和基本面过滤搭配使用。"
        : "支持常见的趋势破位、死叉和超买类卖出信号。";

    return (
      <div className="signal-panel" key={side}>
        <div className="signal-panel-head">
          <h4>{label}</h4>
          <div className="signal-panel-tools">
            <span className="muted">{helper}</span>
            <div className="field-line">
              <label className="inline-radio">
                <input
                  type="radio"
                  checked={customization[side].logic === "and"}
                  onChange={() => updateRuleSet(side, { ...customization[side], logic: "and" })}
                />
                全部满足
              </label>
              <label className="inline-radio">
                <input
                  type="radio"
                  checked={customization[side].logic === "or"}
                  onChange={() => updateRuleSet(side, { ...customization[side], logic: "or" })}
                />
                任一满足
              </label>
            </div>
          </div>
        </div>
        <div className="condition-list">
          {selectedTechnicalDefs.length === 0 ? (
            <div className="muted">请先在上方勾选需要参与策略的技术面因子。</div>
          ) : null}
          {selectedTechnicalDefs.map((item) => {
            const options = TECHNICAL_OPTIONS[side][item.field] || [];
            if (options.length === 0) {
              return (
                <div key={`${side}-${item.field}`} className="condition-row">
                  <strong>{item.label}</strong>
                  <span className="muted">
                    {side === "buy" ? "当前没有可配置的买入规则。" : "当前没有可配置的卖出规则。"}
                  </span>
                </div>
              );
            }
            return (
              <div key={`${side}-${item.field}`} className="condition-row">
                <strong>{item.label}</strong>
                <div className="preset-wrap">
                  {options.map((option) => {
                    const id = technicalConditionId(option.condition);
                    const active = customization[side].technicals.some((cond) => cond.id === id);
                    return (
                      <button
                        key={`${side}-${item.field}-${id}`}
                        type="button"
                        className={active ? "chip active" : "chip"}
                        onClick={() => toggleTechnical(side, option.label, option.condition)}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          {side === "sell" &&
          customization.sell.fundamentals.every((item) => !item.enabled) &&
          customization.sell.technicals.length === 0 ? (
            <div className="muted">当前未显式设置卖出条件，运行回测时将继续沿用模板默认卖出逻辑。</div>
          ) : null}
        </div>
      </div>
    );
  };

  return (
    <div className="page-stack">
      <section className="card strategy-ideas-card">
        <div className="strategy-ideas-head">
          <div>
            <h2>AI 生成推荐策略</h2>
            <p className="muted">
              基于已有回测任务做总结，给出沿着当前有效思路增强的语义策略示例，以及其他风格的备选示例。
            </p>
          </div>
          <button type="button" className="btn primary" onClick={generateStrategyIdeas} disabled={ideasLoading}>
            {ideasLoading ? "生成中..." : "AI 生成推荐策略"}
          </button>
        </div>

        {ideasError ? <div className="error-box">{ideasError}</div> : null}

        {strategyIdeas ? (
          <div className="strategy-ideas-body">
            <div className="strategy-summary">
              <div className="strategy-summary-main">
                <h3>当前回测任务总结</h3>
                <p>{strategyIdeas.summary.narrative}</p>
              </div>
              <div className="strategy-summary-metrics">
                <div className="stat compact">
                  <span>参考任务数</span>
                  <strong>{strategyIdeas.summary.task_count}</strong>
                </div>
                <div className="stat compact">
                  <span>已完成任务</span>
                  <strong>{strategyIdeas.summary.completed_count}</strong>
                </div>
                <div className="stat compact">
                  <span>最佳总收益</span>
                  <strong>{metricPercent(strategyIdeas.summary.best_metrics.totalReturn)}</strong>
                </div>
                <div className="stat compact">
                  <span>最佳回撤</span>
                  <strong>{metricPercent(strategyIdeas.summary.best_metrics.maxDrawdown)}</strong>
                </div>
                <div className="stat compact">
                  <span>最佳夏普</span>
                  <strong>{metric(strategyIdeas.summary.best_metrics.sharpeRatio)}</strong>
                </div>
              </div>
              <div className="strategy-highlight-list">
                {strategyIdeas.summary.highlights.map((item) => (
                  <div key={item} className="strategy-highlight">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="strategy-example-grid">
              <div className="strategy-example-block">
                <h3>沿当前强势思路增强</h3>
                <div className="strategy-example-list">
                  {strategyIdeas.enhancement_examples.map((example) => (
                    <div key={example} className="strategy-example-row">
                      <div>{example}</div>
                      <button type="button" onClick={() => setSemanticText(example)}>
                        填入语义框
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="strategy-example-block">
                <h3>尝试其他策略风格</h3>
                <div className="strategy-example-list">
                  {strategyIdeas.diversified_examples.map((example) => (
                    <div key={example} className="strategy-example-row">
                      <div>{example}</div>
                      <button type="button" onClick={() => setSemanticText(example)}>
                        填入语义框
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className="card">
        <h2>语义策略输入</h2>
        <p className="muted">
          自然语言描述会自动识别买入条件、卖出条件、持有周期和基准，并把匹配到的平台已有因子直接勾选和回填。
        </p>
        <div className="field-column">
          <textarea
            rows={5}
            value={semanticText}
            onChange={(event) => setSemanticText(event.target.value)}
            placeholder={DEFAULT_SEMANTIC_TEXT}
          />
          <div className="cta-row">
            <button type="button" className="btn primary" onClick={runSemantic} disabled={semanticLoading}>
              {semanticLoading ? "分析中..." : "开始语义分析"}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => applySemanticFactors()}
              disabled={!semanticResult || !semanticResult.supported}
            >
              应用语义建议
            </button>
          </div>
        </div>

        {semanticResult ? (
          <div className="semantic-result">
            <div className={semanticResult.supported ? "semantic-ok" : "semantic-bad"}>{semanticResult.message}</div>
            {semanticAutoApplied ? <div className="muted">{semanticAutoApplied}</div> : null}
            {semanticResult.recommended_existing_factors.length > 0 ? (
              <div>
                <strong>可复用因子</strong>
                <div className="preset-wrap">
                  {semanticResult.recommended_existing_factors.map((item) => (
                    <span key={item} className="chip active">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {semanticResult.required_new_factors.length > 0 ? (
              <div>
                <strong>新增因子判定</strong>
                <div className="condition-list">
                  {semanticResult.required_new_factors.map((item) => (
                    <div key={`${item.name}-${item.reason}`} className="condition-row">
                      <div className="field-line">
                        <strong>{item.name || "未命名因子"}</strong>
                        <span className={item.writable ? "tag-on" : "tag-off"}>{item.writable ? "可实现" : "暂不支持"}</span>
                      </div>
                      <div className="muted">{item.description || "-"}</div>
                      <div className="muted">{item.reason || "-"}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        <h3>选股范围与检索</h3>
        <div className="field-line">
          <input placeholder="搜索因子名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
        </div>
        <ChipGroup
          options={factorMeta.ranges}
          selected={selections.ranges}
          onChange={(next) => setSelections({ ...selections, ranges: next })}
        />
      </section>

      <section className="card">
        <h3>基本面因子</h3>
        <ChipGroup
          options={filteredFundamental}
          selected={selections.fundamentals}
          onChange={(next) => setSelections({ ...selections, fundamentals: next })}
        />
        <div className="dual-signal-grid">
          {renderFundamentalPanel("buy")}
          {renderFundamentalPanel("sell")}
        </div>
      </section>

      <section className="card">
        <h3>技术面因子</h3>
        <ChipGroup
          options={filteredTechnical}
          selected={selections.technicals}
          onChange={(next) => setSelections({ ...selections, technicals: next })}
        />
        <div className="dual-signal-grid">
          {renderTechnicalPanel("buy")}
          {renderTechnicalPanel("sell")}
        </div>
      </section>
    </div>
  );
}
