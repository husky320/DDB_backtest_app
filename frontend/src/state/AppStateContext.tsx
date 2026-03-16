import React, { createContext, useContext, useState } from "react";
import type { BacktestResult, FactorMeta, TemplateId, TemplateMeta } from "../types";

type AppSelections = {
  ranges: string[];
  fundamentals: string[];
  technicals: string[];
};

type AppStateContextValue = {
  templates: TemplateMeta[];
  setTemplates: React.Dispatch<React.SetStateAction<TemplateMeta[]>>;
  templateId: TemplateId;
  setTemplateId: React.Dispatch<React.SetStateAction<TemplateId>>;
  config: Record<string, unknown>;
  setConfig: React.Dispatch<React.SetStateAction<Record<string, unknown>>>;
  mergeConfig: (patch: Record<string, unknown>) => void;
  factorMeta: FactorMeta | null;
  setFactorMeta: React.Dispatch<React.SetStateAction<FactorMeta | null>>;
  selections: AppSelections;
  setSelections: React.Dispatch<React.SetStateAction<AppSelections>>;
  lastResult: BacktestResult | null;
  setLastResult: React.Dispatch<React.SetStateAction<BacktestResult | null>>;
};

const AppStateContext = createContext<AppStateContextValue | null>(null);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepMerge(
  base: Record<string, unknown>,
  patch: Record<string, unknown>
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base };
  for (const [key, value] of Object.entries(patch)) {
    const current = next[key];
    if (isPlainObject(current) && isPlainObject(value)) {
      next[key] = deepMerge(current, value);
    } else {
      next[key] = value;
    }
  }
  return next;
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [templateId, setTemplateId] = useState<TemplateId>("combo_01");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [factorMeta, setFactorMeta] = useState<FactorMeta | null>(null);
  const [selections, setSelections] = useState<AppSelections>({
    ranges: [],
    fundamentals: [],
    technicals: [],
  });
  const [lastResult, setLastResult] = useState<BacktestResult | null>(null);

  const mergeConfig = (patch: Record<string, unknown>) => {
    setConfig((prev) => deepMerge(prev, patch));
  };

  return (
    <AppStateContext.Provider
      value={{
        templates,
        setTemplates,
        templateId,
        setTemplateId,
        config,
        setConfig,
        mergeConfig,
        factorMeta,
        setFactorMeta,
        selections,
        setSelections,
        lastResult,
        setLastResult,
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState(): AppStateContextValue {
  const value = useContext(AppStateContext);
  if (!value) {
    throw new Error("useAppState must be used inside AppStateProvider");
  }
  return value;
}

