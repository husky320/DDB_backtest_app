from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request

_OPENER = request.build_opener(request.ProxyHandler({}))


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any] | list[Any] | None, str]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = request.Request(url=url, data=data, headers=headers, method=method.upper())

    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = int(resp.status)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
        return status, None, body

    if not body.strip():
        return status, None, body
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, body
    return status, parsed, body


def _request_text(url: str, timeout: int = 60) -> tuple[int, str]:
    req = request.Request(url=url, headers={"Accept": "text/plain"}, method="GET")
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _find_run_with_trades(base_url: str, items: list[dict[str, Any]]) -> str | None:
    for item in items:
        run_id = str(item.get("run_id", "")).strip()
        if not run_id:
            continue
        status, payload, _ = _request_json("GET", f"{base_url}/backtests/{parse.quote(run_id)}")
        if status != 200 or not isinstance(payload, dict):
            continue
        result = payload.get("result") or {}
        trades = result.get("trades") or []
        if isinstance(trades, list) and trades:
            return run_id
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run comprehensive regression checks with UTF-8 safe output.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/dolphindb", help="API base URL")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON path. Defaults to runtime_logs/comprehensive_validation_fixed_<timestamp>.json",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    runs_status, runs_payload, runs_raw = _request_json("GET", f"{base_url}/backtests?limit=200")
    runs_items: list[dict[str, Any]] = []
    if runs_status == 200 and isinstance(runs_payload, dict):
        raw_items = runs_payload.get("items", [])
        if isinstance(raw_items, list):
            runs_items = [x for x in raw_items if isinstance(x, dict)]
    run_id_for_csv = _find_run_with_trades(base_url, runs_items)

    csv_status = 0
    csv_first_line = ""
    csv_has_header = False
    if run_id_for_csv:
        csv_status, csv_text = _request_text(f"{base_url}/backtests/{parse.quote(run_id_for_csv)}/trades?format=csv")
        csv_first_line = (csv_text.splitlines() or [""])[0].strip()
        csv_has_header = csv_first_line.startswith("orderId,")

    ai_status, ai_payload, ai_raw = _request_json(
        "POST",
        f"{base_url}/ai/chat",
        payload={"message": "请帮我做实盘下单并自动交易", "current_config": {"template_id": "combo_01"}},
    )
    ai_blocked = bool(isinstance(ai_payload, dict) and ai_payload.get("blocked"))
    ai_reason = str(ai_payload.get("reason", "")) if isinstance(ai_payload, dict) else ""

    semantic_status, semantic_payload, semantic_raw = _request_json(
        "POST",
        f"{base_url}/semantic/analyze",
        payload={"strategy_text": ""},
    )
    semantic_supported = None
    semantic_message = ""
    if isinstance(semantic_payload, dict):
        semantic_supported = semantic_payload.get("supported")
        semantic_message = str(semantic_payload.get("message", ""))

    out = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "checks": {
            "csv_header": {
                "status_code": csv_status,
                "run_id": run_id_for_csv,
                "has_header": csv_has_header,
                "first_line": csv_first_line,
            },
            "ai_blocked": {
                "status_code": ai_status,
                "blocked": ai_blocked,
                "reason": ai_reason,
                "raw_fallback": ai_raw if not isinstance(ai_payload, dict) else "",
            },
            "semantic_empty_text": {
                "status_code": semantic_status,
                "supported": semantic_supported,
                "message": semantic_message,
                "raw_fallback": semantic_raw if not isinstance(semantic_payload, dict) else "",
            },
        },
        "assertions": {
            "csv_header_ok": bool(run_id_for_csv and csv_status == 200 and csv_has_header),
            "ai_block_ok": bool(ai_status == 200 and ai_blocked),
            "semantic_empty_ok": bool(semantic_status == 200 and semantic_supported is False),
        },
        "debug": {
            "runs_status": runs_status,
            "runs_count": len(runs_items),
            "runs_raw_fallback": runs_raw if not isinstance(runs_payload, dict) else "",
        },
    }

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).resolve().parents[1] / "runtime_logs" / f"comprehensive_validation_fixed_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(str(output_path))
    print(json.dumps(out["assertions"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
