export type TemplateId = "combo_01" | "combo_02" | "combo_03" | "timing_13";

export interface TemplateMeta {
  template_id: TemplateId;
  label: string;
  strategy_type: "combo" | "timing";
  default_config: Record<string, unknown>;
}

export interface DDBConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  candidate_ports: number[];
  preferred_data_node: string;
  has_password?: boolean;
}

export interface DDBStatus {
  config: DDBConfig;
  active_data_node: string;
  nodes: Array<{
    host: string;
    port: number;
    alias: string;
    can_load_dfs: boolean;
    available: boolean;
    error: string;
  }>;
}

export interface LLMConfig {
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  temperature: number;
  max_tokens: number;
  enabled: boolean;
  has_api_key?: boolean;
}

export interface BacktestResult {
  run_id: string;
  template_id: TemplateId;
  status: string;
  degraded?: boolean;
  degraded_reasons?: string[];
  warnings: string[];
  applied_config?: Record<string, unknown>;
  no_trade?: boolean;
  no_trade_reason?: string;
  kpis: Record<string, number>;
  summary: Record<string, unknown>;
  equity: Array<{
    tradeDate: string;
    portfolioValue: number | null;
    benchmarkValue: number | null;
  }>;
  trades: Array<Record<string, unknown>>;
  tables: Record<string, unknown>;
  execution?: {
    started_at?: string;
    finished_at?: string;
    duration_ms?: number;
  };
  code_files?: Array<{
    name: string;
    kind: string;
    included: boolean;
    content: string;
  }>;
}

export interface BacktestRunStart {
  run_id: string;
  status: string;
}

export interface BacktestTaskSummary {
  run_id: string;
  template_id: TemplateId | string;
  strategy_label?: string;
  status: "running" | "completed" | "degraded" | "failed" | string;
  error?: string | null;
  error_detail?: string | null;
  error_info?: {
    title: string;
    summary: string;
    suggestion: string;
    code: string;
  } | null;
  created_at?: string;
  started_at?: string;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface BacktestTaskDetail extends BacktestTaskSummary {
  request?: Record<string, unknown>;
  result?: BacktestResult | null;
}

export interface TradePageResponse {
  page: number;
  page_size: number;
  total: number;
  items: Array<Record<string, unknown>>;
}

export interface AIChatResponse {
  allowed_actions: string[];
  blocked: boolean;
  reason?: string;
  config_patch: Record<string, unknown>;
  trigger_run?: boolean;
  applied_actions?: string[];
  hint: string;
  examples: string[];
}

export interface AIRecommendResponse {
  skills: string[];
  config_patch: Record<string, unknown>;
  hints: string[];
}

export interface StrategyIdeaSummary {
  task_count: number;
  completed_count: number;
  best_run_id: string;
  best_template_id: string;
  narrative: string;
  highlights: string[];
  best_metrics: Record<string, number>;
}

export interface StrategyIdeaResponse {
  summary: StrategyIdeaSummary;
  enhancement_examples: string[];
  diversified_examples: string[];
}

export interface SemanticAnalyzeResponse {
  supported: boolean;
  framework_supported: boolean;
  message: string;
  required_new_factors: Array<{
    name: string;
    description: string;
    writable: boolean;
    reason: string;
  }>;
  recommended_existing_factors: string[];
}

export interface FactorMeta {
  ranges: string[];
  fundamental_factors: Array<{ label: string; field: string }>;
  technical_factors: Array<{ label: string; field: string }>;
  timing_signal_map: Record<string, string[]>;
}

export interface FundamentalCondition {
  id: string;
  label: string;
  field: string;
  op: "<" | "<=" | ">" | ">=" | "==" | "!=";
  value: number;
  enabled: boolean;
}

export interface TechnicalCondition {
  id: string;
  label: string;
  type:
    | "ma_above"
    | "ma_below"
    | "ma_bull_arrangement"
    | "macd_golden"
    | "macd_dead"
    | "rsi_threshold"
    | "kdj_golden"
    | "kdj_dead"
    | "boll_break_upper"
    | "boll_break_lower"
    | "bbi_break";
  period?: number;
  op?: "<" | "<=" | ">" | ">=" | "==" | "!=";
  value?: number;
  enabled: boolean;
}

export interface FactorRuleSet {
  logic: "and" | "or";
  fundamentals: FundamentalCondition[];
  technicals: TechnicalCondition[];
}

export interface FactorCustomization {
  buy: FactorRuleSet;
  sell: FactorRuleSet;
}
