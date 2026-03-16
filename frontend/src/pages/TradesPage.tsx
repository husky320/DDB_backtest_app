import React, { useMemo, useState } from "react";
import { useAppState } from "../state/AppStateContext";

export function TradesPage() {
  const { lastResult } = useAppState();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const data = lastResult?.trades ?? [];
  const columns = useMemo(() => (data[0] ? Object.keys(data[0]) : []), [data]);
  const total = data.length;
  const start = (page - 1) * pageSize;
  const end = Math.min(total, start + pageSize);
  const pageRows = data.slice(start, end);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (!lastResult) {
    return <div className="card">暂无交易明细，请先运行回测。</div>;
  }

  return (
    <div className="page-stack">
      <section className="card">
        <h2>历史交易明细</h2>
        <p className="muted">
          第 {page} / {totalPages} 页，共 {total} 条
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row, index) => (
                <tr key={index}>
                  {columns.map((col) => (
                    <td key={col}>{String((row as Record<string, unknown>)[col] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pager">
          <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
            上一页
          </button>
          <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
            下一页
          </button>
        </div>
      </section>
    </div>
  );
}
