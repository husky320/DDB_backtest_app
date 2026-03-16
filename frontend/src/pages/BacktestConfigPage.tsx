import React, { startTransition, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { runBacktest } from "../api/client";
import { AIAssistantModal } from "../components/AIAssistantModal";
import { useAppState } from "../state/AppStateContext";
import type { TemplateId } from "../types";

const quickRanges = [
  { label: "近三年", years: 3 },
  { label: "近一年", years: 1 },
  { label: "近三个月", months: 3 },
  { label: "近一个月", months: 1 },
];

export function BacktestConfigPage() {
  const { templateId, setTemplateId, templates, config, mergeConfig, setLastResult } = useAppState();
  const navigate = useNavigate();
  const [running, setRunning] = useState(false);
  const [errMsg, setErrMsg] = useState("");
  const [aiOpen, setAiOpen] = useState(false);

  const startDate = String(config["startDate"] || "2023.03.10").replace(/\./g, "-");
  const endDate = String(config["endDate"] || "2026.03.10").replace(/\./g, "-");

  const factorCustomizationSummary = useMemo(() => {
    const raw = config.factorCustomization;
    if (!raw || typeof raw !== "object") return "默认（未启用个性化规则）";
    const customized = raw as {
      buy?: { fundamentals?: Array<{ enabled?: boolean }>; technicals?: Array<unknown>; logic?: "and" | "or" };
      sell?: { fundamentals?: Array<{ enabled?: boolean }>; technicals?: Array<unknown>; logic?: "and" | "or" };
      fundamentals?: Array<{ enabled?: boolean }>;
      technicals?: Array<unknown>;
      logic?: "and" | "or";
    };
    const buy = customized.buy || customized;
    const sell = customized.sell || {};
    const buyFundamentalCount = Array.isArray(buy.fundamentals) ? buy.fundamentals.filter((item) => item.enabled).length : 0;
    const buyTechnicalCount = Array.isArray(buy.technicals) ? buy.technicals.length : 0;
    const sellFundamentalCount = Array.isArray(sell.fundamentals)
      ? sell.fundamentals.filter((item) => item.enabled).length
      : 0;
    const sellTechnicalCount = Array.isArray(sell.technicals) ? sell.technicals.length : 0;
    if (buyFundamentalCount + buyTechnicalCount + sellFundamentalCount + sellTechnicalCount === 0) {
      return "默认（未启用个性化规则）";
    }
    const buyLogicText = buy.logic === "or" ? "任一满足" : "全部满足";
    const sellLogicText = sell.logic === "or" ? "任一满足" : "全部满足";
    return `买入：基本面 ${buyFundamentalCount} 条，技术面 ${buyTechnicalCount} 条，逻辑 ${buyLogicText}；卖出：基本面 ${sellFundamentalCount} 条，技术面 ${sellTechnicalCount} 条，逻辑 ${sellLogicText}`;
  }, [config.factorCustomization]);

  const applyQuickRange = (item: { years?: number; months?: number }) => {
    const now = new Date();
    const start = new Date(now);
    if (item.years) start.setFullYear(start.getFullYear() - item.years);
    if (item.months) start.setMonth(start.getMonth() - item.months);
    mergeConfig({
      startDate: start.toISOString().slice(0, 10).replace(/-/g, "."),
      endDate: now.toISOString().slice(0, 10).replace(/-/g, "."),
    });
  };

  const run = async () => {
    setRunning(true);
    setErrMsg("");
    try {
      const started = await runBacktest({
        template_id: templateId,
        user_config: config,
        auto_fallback_benchmark: true,
      });
      startTransition(() => {
        setLastResult(null);
        navigate(`/tasks?run_id=${started.run_id}`);
      });
    } catch (error: any) {
      setErrMsg(error?.response?.data?.detail || "回测提交失败，请检查参数或后端连接。");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page-stack">
      <section className="card">
        <h2>回测参数配置</h2>
        <p className="muted">配置区间、基准、仓位与模板后，提交到任务队列并支持并行运行。</p>
      </section>

      <section className="card">
        <h3>基础参数</h3>
        <div className="field-line">
          <label>策略模板</label>
          <select value={templateId} onChange={(e) => setTemplateId(e.target.value as TemplateId)}>
            {templates.map((item) => (
              <option key={item.template_id} value={item.template_id}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid-2">
          <div className="field-column">
            <label>开始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => mergeConfig({ startDate: e.target.value.replace(/-/g, ".") })}
            />
          </div>
          <div className="field-column">
            <label>结束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => mergeConfig({ endDate: e.target.value.replace(/-/g, ".") })}
            />
          </div>
        </div>
        <div className="quick-range">
          {quickRanges.map((item) => (
            <button key={item.label} type="button" onClick={() => applyQuickRange(item)}>
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>买卖与基准</h3>
        <div className="grid-2">
          <div className="field-column">
            <label>对比基准</label>
            <select
              value={String(config["benchmark"] || "000002.SZ")}
              onChange={(e) => mergeConfig({ benchmark: e.target.value })}
            >
              <option value="000002.SZ">万科 A (000002.SZ)</option>
              <option value="000300.SH">沪深 300 (000300.SH)</option>
            </select>
          </div>
          <div className="field-column">
            <label>买入优先级</label>
            <select
              value={String((config["buyPriority"] as string[] | undefined)?.[0] || "pct_chg")}
              onChange={(e) => mergeConfig({ buyPriority: [e.target.value] })}
            >
              <option value="pct_chg">涨幅由大到小</option>
              <option value="amount">成交额由大到小</option>
              <option value="pe">市盈率由小到大</option>
            </select>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>仓位风控</h3>
        <div className="grid-2">
          <div className="field-column">
            <label>初始资金</label>
            <input
              type="number"
              value={String(config["cash"] || 1000000)}
              onChange={(e) => mergeConfig({ cash: Number(e.target.value) })}
            />
          </div>
          <div className="field-column">
            <label>持股周期（天）</label>
            <input
              type="number"
              value={String(config["holdingPeriod"] || 20)}
              onChange={(e) => mergeConfig({ holdingPeriod: Number(e.target.value) })}
            />
          </div>
          <div className="field-column">
            <label>个股最大仓位</label>
            <input
              type="number"
              step="0.01"
              value={String(config["perStockPercent"] || 0.1)}
              onChange={(e) => mergeConfig({ perStockPercent: Number(e.target.value) })}
            />
          </div>
          <div className="field-column">
            <label>账户最大持仓数</label>
            <input
              type="number"
              value={String(config["maxPositionLimit"] || 5)}
              onChange={(e) => mergeConfig({ maxPositionLimit: Number(e.target.value) })}
            />
          </div>
          <div className="field-column">
            <label>单日最大买入数</label>
            <input
              type="number"
              value={String(config["dailyBuyCountLimit"] || 2)}
              onChange={(e) => mergeConfig({ dailyBuyCountLimit: Number(e.target.value) })}
            />
          </div>
        </div>
      </section>

      <section className="card">
        <h3>因子个性化状态</h3>
        <p className="muted">{factorCustomizationSummary}</p>
      </section>

      {errMsg ? <div className="error-box">{errMsg}</div> : null}

      <section className="cta-row">
        <button type="button" className="btn" onClick={() => setAiOpen(true)}>
          智能助手
        </button>
        <button type="button" className="btn primary" onClick={run} disabled={running}>
          {running ? "提交中..." : "提交回测任务"}
        </button>
      </section>

      <AIAssistantModal open={aiOpen} onClose={() => setAiOpen(false)} />
    </div>
  );
}
