import React, { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { fetchFactorMeta, fetchTemplates } from "./api/client";
import { AppShell } from "./components/AppShell";
import { AnalysisPage } from "./pages/AnalysisPage";
import { BacktestConfigPage } from "./pages/BacktestConfigPage";
import { FactorBuilderPage } from "./pages/FactorBuilderPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useAppState } from "./state/AppStateContext";

export default function App() {
  const {
    templates,
    setTemplates,
    templateId,
    setTemplateId,
    config,
    setConfig,
    factorMeta,
    setFactorMeta
  } = useAppState();

  useEffect(() => {
    fetchTemplates()
      .then((items) => {
        setTemplates(items);
        if (!items.find((item) => item.template_id === templateId)) {
          setTemplateId(items[0]?.template_id ?? "combo_01");
        }
      })
      .catch(() => undefined);
  }, [setTemplates, setTemplateId, templateId]);

  useEffect(() => {
    if (factorMeta) return;
    fetchFactorMeta().then(setFactorMeta).catch(() => undefined);
  }, [factorMeta, setFactorMeta]);

  useEffect(() => {
    const selected = templates.find((item) => item.template_id === templateId);
    if (!selected) return;
    if (Object.keys(config).length === 0) {
      setConfig(selected.default_config);
      return;
    }
    setConfig((prev) => ({ ...selected.default_config, ...prev }));
  }, [templateId, templates, setConfig]);

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/factors" replace />} />
        <Route path="/factors" element={<FactorBuilderPage />} />
        <Route path="/backtest" element={<BacktestConfigPage />} />
        <Route path="/tasks" element={<AnalysisPage />} />
        <Route path="/analysis" element={<Navigate to="/tasks" replace />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </AppShell>
  );
}
