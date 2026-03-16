import React, { useState } from "react";
import { chatAI, recommendAI } from "../api/client";
import { useAppState } from "../state/AppStateContext";

interface AIAssistantModalProps {
  open: boolean;
  onClose: () => void;
}

export function AIAssistantModal({ open, onClose }: AIAssistantModalProps) {
  const { config, mergeConfig, templateId, selections } = useAppState();
  const [goal, setGoal] = useState("稳健收益");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState("");
  const [patchPreview, setPatchPreview] = useState<Record<string, unknown> | null>(null);
  const [examples, setExamples] = useState<string[]>([]);

  if (!open) return null;

  const runRecommend = async () => {
    setBusy(true);
    try {
      const response = await recommendAI({
        template_id: templateId,
        selected_ranges: selections.ranges,
        selected_fundamental_factors: selections.fundamentals,
        selected_technical_factors: selections.technicals,
        goal,
        current_config: config,
      });
      setPatchPreview(response.config_patch);
      setHint(response.hints.join(" "));
    } catch {
      setHint("规则推荐失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  const runChat = async () => {
    if (!message.trim()) return;
    setBusy(true);
    try {
      const response = await chatAI({
        message,
        current_config: config,
      });
      setPatchPreview(response.config_patch);
      setHint(response.blocked ? response.reason || response.hint : response.hint);
      setExamples(response.examples || []);
    } catch {
      setHint("对话调用失败，请检查后端连接。");
    } finally {
      setBusy(false);
    }
  };

  const applyPatch = () => {
    if (!patchPreview) return;
    mergeConfig(patchPreview);
    setHint("配置补丁已应用到当前策略。");
  };

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-head">
          <h3>智能助手</h3>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </div>

        <p className="muted">
          支持动作：改参数、改因子、改基准、改区间、切模板、触发回测。超出白名单能力会被拦截。
        </p>

        <div className="field-line">
          <label>优化目标</label>
          <input value={goal} onChange={(e) => setGoal(e.target.value)} />
          <button type="button" onClick={runRecommend} disabled={busy}>
            规则推荐
          </button>
        </div>

        <div className="field-column">
          <label>对话输入</label>
          <textarea
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="例如：将回测区间设为 2023-01-01 到 2023-12-31，最大持仓数改为 10，并触发回测。"
          />
          <button type="button" onClick={runChat} disabled={busy}>
            发送
          </button>
        </div>

        {examples.length > 0 && (
          <div className="examples">
            <h4>可提问示例</h4>
            {examples.map((item) => (
              <div key={item} className="example-row">
                {item}
              </div>
            ))}
          </div>
        )}

        {patchPreview && (
          <div className="patch-box">
            <h4>配置补丁</h4>
            <pre>{JSON.stringify(patchPreview, null, 2)}</pre>
            <button type="button" onClick={applyPatch}>
              应用补丁
            </button>
          </div>
        )}

        {hint ? <div className="hint">{hint}</div> : null}
      </div>
    </div>
  );
}
