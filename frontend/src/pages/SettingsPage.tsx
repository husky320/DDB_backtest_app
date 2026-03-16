import React, { useEffect, useState } from "react";
import { fetchDDBConfig, fetchLLMConfig, updateDDBConfig, updateLLMConfig } from "../api/client";
import type { DDBConfig, LLMConfig } from "../types";

const defaultDDB: DDBConfig = {
  host: "183.134.101.135",
  port: 8030,
  username: "admin",
  password: "",
  candidate_ports: [8030, 8031, 8032, 8033],
  preferred_data_node: "",
  has_password: false,
};

const defaultLLM: LLMConfig = {
  provider: "deepseek",
  base_url: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  api_key: "",
  temperature: 0.2,
  max_tokens: 1200,
  enabled: true,
  has_api_key: false,
};

export function SettingsPage() {
  const [ddb, setDdb] = useState<DDBConfig>(defaultDDB);
  const [llm, setLlm] = useState<LLMConfig>(defaultLLM);
  const [statusText, setStatusText] = useState("");
  const [saving, setSaving] = useState(false);
  const hasDDBPassword = Boolean(ddb.has_password);
  const hasLLMApiKey = Boolean(llm.has_api_key);

  useEffect(() => {
    fetchDDBConfig()
      .then((data) => {
        setDdb({ ...data.config, password: "" });
      })
      .catch(() => undefined);
    fetchLLMConfig()
      .then((data) => {
        setLlm({ ...data, api_key: "" });
      })
      .catch(() => undefined);
  }, []);

  const saveDDB = async () => {
    setSaving(true);
    try {
      const { has_password, ...raw } = ddb;
      const payload: DDBConfig = {
        ...raw,
        password: ddb.password.trim(),
        candidate_ports: Array.from(new Set(raw.candidate_ports)).filter((x) => Number.isFinite(x)),
      };
      const resp = await updateDDBConfig(payload);
      setDdb({ ...resp.config, password: "" });
      setStatusText("DolphinDB 连接配置已保存。");
    } catch (error: any) {
      setStatusText(error?.response?.data?.detail || "DolphinDB 配置保存失败。");
    } finally {
      setSaving(false);
    }
  };

  const saveLLM = async () => {
    setSaving(true);
    try {
      const { has_api_key, ...raw } = llm;
      const resp = await updateLLMConfig({ ...raw, api_key: llm.api_key.trim() });
      setLlm({ ...resp.config, api_key: "" });
      setStatusText("LLM 模型配置已保存。");
    } catch (error: any) {
      setStatusText(error?.response?.data?.detail || "LLM 配置保存失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-stack">
      <section className="card">
        <h2>创建配置</h2>
        <p className="muted">统一管理 DolphinDB Server 与 LLM 厂商接入参数，支持 DeepSeek API Key 直连。</p>
      </section>

      <section className="card">
        <h3>DolphinDB Server</h3>
        <div className="grid-2">
          <div className="field-column">
            <label>Host</label>
            <input value={ddb.host} onChange={(e) => setDdb({ ...ddb, host: e.target.value })} />
          </div>
          <div className="field-column">
            <label>Port</label>
            <input
              type="number"
              value={ddb.port}
              onChange={(e) => setDdb({ ...ddb, port: Number(e.target.value) || 0 })}
            />
          </div>
          <div className="field-column">
            <label>Username</label>
            <input value={ddb.username} onChange={(e) => setDdb({ ...ddb, username: e.target.value })} />
          </div>
          <div className="field-column">
            <label>Password</label>
            <input
              type="password"
              value={ddb.password}
              placeholder={hasDDBPassword ? "已配置（留空则保持不变）" : "请输入密码"}
              onChange={(e) => setDdb({ ...ddb, password: e.target.value })}
            />
            {hasDDBPassword ? <span className="muted">密码已配置，出于安全原因不会回显。</span> : null}
          </div>
          <div className="field-column">
            <label>Candidate Ports（逗号分隔）</label>
            <input
              value={ddb.candidate_ports.join(",")}
              onChange={(e) =>
                setDdb({
                  ...ddb,
                  candidate_ports: e.target.value
                    .split(",")
                    .map((x) => Number(x.trim()))
                    .filter((x) => Number.isFinite(x)),
                })
              }
            />
          </div>
          <div className="field-column">
            <label>Preferred Data Node Alias</label>
            <input
              value={ddb.preferred_data_node}
              onChange={(e) => setDdb({ ...ddb, preferred_data_node: e.target.value })}
            />
          </div>
        </div>
        <div className="cta-row">
          <button type="button" className="btn primary" onClick={saveDDB} disabled={saving}>
            保存 DolphinDB 配置
          </button>
        </div>
      </section>

      <section className="card">
        <h3>LLM 模型厂商</h3>
        <div className="grid-2">
          <div className="field-column">
            <label>Provider</label>
            <select value={llm.provider} onChange={(e) => setLlm({ ...llm, provider: e.target.value })}>
              <option value="deepseek">deepseek</option>
              <option value="openai">openai-compatible</option>
            </select>
          </div>
          <div className="field-column">
            <label>Base URL</label>
            <input value={llm.base_url} onChange={(e) => setLlm({ ...llm, base_url: e.target.value })} />
          </div>
          <div className="field-column">
            <label>Model</label>
            <input value={llm.model} onChange={(e) => setLlm({ ...llm, model: e.target.value })} />
          </div>
          <div className="field-column">
            <label>API Key</label>
            <input
              type="password"
              value={llm.api_key}
              placeholder={hasLLMApiKey ? "已配置（留空则保持不变）" : "请输入 API Key"}
              onChange={(e) => setLlm({ ...llm, api_key: e.target.value })}
            />
            {hasLLMApiKey ? <span className="muted">API Key 已配置，出于安全原因不会回显。</span> : null}
          </div>
          <div className="field-column">
            <label>Temperature</label>
            <input
              type="number"
              step="0.1"
              value={llm.temperature}
              onChange={(e) => setLlm({ ...llm, temperature: Number(e.target.value) })}
            />
          </div>
          <div className="field-column">
            <label>Max Tokens</label>
            <input
              type="number"
              value={llm.max_tokens}
              onChange={(e) => setLlm({ ...llm, max_tokens: Number(e.target.value) })}
            />
          </div>
          <div className="field-line">
            <label className="toggle-line">
              <input
                type="checkbox"
                checked={llm.enabled}
                onChange={(e) => setLlm({ ...llm, enabled: e.target.checked })}
              />
              <span>启用语义模型能力</span>
            </label>
          </div>
        </div>
        <div className="cta-row">
          <button type="button" className="btn primary" onClick={saveLLM} disabled={saving}>
            保存 LLM 配置
          </button>
        </div>
      </section>

      {statusText ? (
        <section className="card">
          <div className="muted">{statusText}</div>
        </section>
      ) : null}
    </div>
  );
}
