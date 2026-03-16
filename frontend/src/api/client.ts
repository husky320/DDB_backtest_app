import axios from "axios";
import {
  AIChatResponse,
  AIRecommendResponse,
  BacktestResult,
  BacktestTaskDetail,
  BacktestRunStart,
  BacktestTaskSummary,
  DDBConfig,
  DDBStatus,
  FactorMeta,
  LLMConfig,
  SemanticAnalyzeResponse,
  StrategyIdeaResponse,
  TemplateMeta,
} from "../types";

const api = axios.create({
  baseURL: "/api/dolphindb",
  timeout: 300000
});

const directApi = axios.create({
  baseURL: `${window.location.protocol}//${window.location.hostname}:8000/api/dolphindb`,
  timeout: 300000
});

function shouldFallback(error: any): boolean {
  if (!error) return false;
  if (!error.response) return true;
  return Number(error.response.status || 0) >= 500;
}

async function requestWithFallback<T>(
  method: "get" | "post" | "delete",
  url: string,
  payload?: unknown,
  params?: Record<string, unknown>
): Promise<T> {
  try {
    const response =
      method === "get"
        ? await api.get<T>(url, { params })
        : method === "delete"
          ? await api.delete<T>(url, { params, data: payload })
          : await api.post<T>(url, payload, { params });
    return response.data;
  } catch (error: any) {
    if (!shouldFallback(error)) {
      throw error;
    }
    const response =
      method === "get"
        ? await directApi.get<T>(url, { params })
        : method === "delete"
          ? await directApi.delete<T>(url, { params, data: payload })
          : await directApi.post<T>(url, payload, { params });
    return response.data;
  }
}

export async function fetchTemplates(): Promise<TemplateMeta[]> {
  const data = await requestWithFallback<{ templates: TemplateMeta[] }>("get", "/meta/templates");
  return data.templates;
}

export async function fetchDDBConfig(): Promise<DDBStatus> {
  return requestWithFallback<DDBStatus>("get", "/config/ddb");
}

export async function updateDDBConfig(payload: DDBConfig): Promise<{ ok: boolean; config: DDBConfig; status: DDBStatus }> {
  return requestWithFallback<{ ok: boolean; config: DDBConfig; status: DDBStatus }>("post", "/config/ddb", payload);
}

export async function fetchLLMConfig(): Promise<LLMConfig> {
  return requestWithFallback<LLMConfig>("get", "/config/llm");
}

export async function updateLLMConfig(payload: LLMConfig): Promise<{ ok: boolean; config: LLMConfig }> {
  return requestWithFallback<{ ok: boolean; config: LLMConfig }>("post", "/config/llm", payload);
}

export async function fetchFactorMeta(): Promise<FactorMeta> {
  return requestWithFallback<FactorMeta>("get", "/meta/factors");
}

export async function runBacktest(payload: {
  template_id: string;
  user_config: Record<string, unknown>;
  ai_patch?: Record<string, unknown>;
  auto_fallback_benchmark?: boolean;
}): Promise<BacktestRunStart> {
  return requestWithFallback<BacktestRunStart>("post", "/backtests/run", payload);
}

export async function fetchRun(runId: string): Promise<BacktestTaskDetail> {
  return requestWithFallback<BacktestTaskDetail>("get", `/backtests/${runId}`);
}

export async function fetchBacktests(limit = 200): Promise<BacktestTaskSummary[]> {
  const data = await requestWithFallback<{ items: BacktestTaskSummary[] }>("get", "/backtests", undefined, { limit });
  return data.items;
}

export async function deleteBacktest(runId: string): Promise<{ ok: boolean; run_id: string }> {
  return requestWithFallback<{ ok: boolean; run_id: string }>("delete", `/backtests/${runId}`);
}

export async function chatAI(payload: { message: string; current_config: Record<string, unknown> }): Promise<AIChatResponse> {
  return requestWithFallback<AIChatResponse>("post", "/ai/chat", payload);
}

export async function recommendAI(payload: {
  mode?: string;
  template_id?: string;
  selected_ranges: string[];
  selected_fundamental_factors: string[];
  selected_technical_factors: string[];
  goal: string;
  current_config: Record<string, unknown>;
  backtest_tasks?: Array<Record<string, unknown>>;
}): Promise<AIRecommendResponse> {
  return requestWithFallback<AIRecommendResponse>("post", "/ai/recommend", payload);
}

export async function analyzeSemanticStrategy(payload: { strategy_text: string }): Promise<SemanticAnalyzeResponse> {
  return requestWithFallback<SemanticAnalyzeResponse>("post", "/semantic/analyze", payload);
}

export async function recommendStrategyIdeas(payload: {
  template_id?: string;
  selected_ranges: string[];
  selected_fundamental_factors: string[];
  selected_technical_factors: string[];
  current_config: Record<string, unknown>;
  backtest_tasks: BacktestTaskDetail[];
}): Promise<StrategyIdeaResponse> {
  return requestWithFallback<StrategyIdeaResponse>("post", "/ai/recommend", {
    ...payload,
    mode: "strategy_ideas",
    goal: "strategy_ideas",
  });
}
