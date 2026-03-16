import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchDDBConfig, fetchLLMConfig } from "../api/client";

const navItems = [
  { to: "/factors", label: "因子页" },
  { to: "/backtest", label: "回测页" },
  { to: "/tasks", label: "任务页" },
  { to: "/settings", label: "配置页" },
];

type StatusKind = "loading" | "ok" | "warn" | "error";

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [ddbKind, setDdbKind] = useState<StatusKind>("loading");
  const [ddbText, setDdbText] = useState("检测中");
  const [llmKind, setLlmKind] = useState<StatusKind>("loading");
  const [llmText, setLlmText] = useState("检测中");

  useEffect(() => {
    let cancelled = false;
    const loadStatus = async () => {
      try {
        const ddb = await fetchDDBConfig();
        if (cancelled) return;
        const hasDataNode = ddb.nodes.some((x) => x.available && x.can_load_dfs);
        if (hasDataNode) {
          setDdbKind("ok");
          setDdbText(`在线 ${ddb.active_data_node || "-"}`);
        } else {
          setDdbKind("warn");
          setDdbText("无可用数据节点");
        }
      } catch {
        if (!cancelled) {
          setDdbKind("error");
          setDdbText("连接失败");
        }
      }

      try {
        const llm = await fetchLLMConfig();
        if (cancelled) return;
        if (!llm.enabled) {
          setLlmKind("warn");
          setLlmText("已禁用");
        } else if (llm.has_api_key || llm.api_key) {
          setLlmKind("ok");
          setLlmText(`${llm.provider}:${llm.model}`);
        } else {
          setLlmKind("warn");
          setLlmText("未配置 Key");
        }
      } catch {
        if (!cancelled) {
          setLlmKind("error");
          setLlmText("配置读取失败");
        }
      }
    };

    loadStatus().catch(() => undefined);
    const timer = window.setInterval(() => loadStatus().catch(() => undefined), 20000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="app-bg">
      <div className="app-container">
        <header className="app-header">
          <div className="header-main">
            <div className="brand-wrap">
              <span className="brand-kicker">DolphinDB · Quant Lab</span>
              <h1>DolphinDB 量化选股择时策略工作台</h1>
              <span className="sub">Backtest Engine + Factor Studio + Task Center</span>
            </div>
            <div className="header-status">
              <div className={`status-pill ${ddbKind}`}>
                <span className="dot" />
                <span>DDB {ddbText}</span>
              </div>
              <div className={`status-pill ${llmKind}`}>
                <span className="dot" />
                <span>LLM {llmText}</span>
              </div>
            </div>
          </div>
        </header>

        <main className="app-main">{children}</main>

        <nav className="app-nav">
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.to);
            return (
              <Link key={item.to} to={item.to} className={active ? "nav-item active" : "nav-item"}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
