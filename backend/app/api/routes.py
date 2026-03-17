from __future__ import annotations

import os
import threading
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.api.schemas import (
    AIChatRequest,
    AIRecommendRequest,
    BacktestRunRequest,
    DDBConfigRequest,
    LLMConfigRequest,
    SemanticAnalyzeRequest,
)
from app.services.container import ServiceContainer

router = APIRouter()


def _container(request: Request) -> ServiceContainer:
    return request.app.state.container  # type: ignore[attr-defined]


@router.get("/config/ddb")
def get_ddb_config(request: Request) -> dict[str, Any]:
    container = _container(request)
    return container.connection.get_status()


@router.post("/config/ddb")
def update_ddb_config(request: Request, payload: DDBConfigRequest) -> dict[str, Any]:
    container = _container(request)
    try:
        cfg = container.connection.update_config(payload.model_dump(), validate_connection=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "config": cfg.to_public_dict(), "status": container.connection.get_status()}


@router.get("/config/llm")
def get_llm_config(request: Request) -> dict[str, Any]:
    container = _container(request)
    return container.llm_config.get_public()


@router.post("/config/llm")
def update_llm_config(request: Request, payload: LLMConfigRequest) -> dict[str, Any]:
    container = _container(request)
    cfg = container.llm_config.update(payload.model_dump())
    return {"ok": True, "config": cfg.to_public_dict()}


@router.get("/meta/templates")
def get_templates(request: Request) -> dict[str, Any]:
    container = _container(request)
    return {"templates": container.registry.list_templates()}


@router.get("/meta/factors")
def get_factors(request: Request) -> dict[str, Any]:
    container = _container(request)
    return container.registry.get_factor_meta()


@router.post("/backtests/run", status_code=status.HTTP_202_ACCEPTED)
def run_backtest(request: Request, payload: BacktestRunRequest) -> dict[str, Any]:
    container = _container(request)
    run_id = str(uuid4())
    container.runs.create(
        run_id=run_id,
        template_id=payload.template_id,
        request_payload=payload.model_dump(),
    )

    def _run_job() -> None:
        try:
            result = container.runner.run(
                run_id=run_id,
                template_id=payload.template_id,
                user_config=payload.user_config,
                ai_patch=payload.ai_patch,
                auto_fallback_benchmark=payload.auto_fallback_benchmark,
            )
            container.runs.complete(run_id, result)
        except Exception as exc:
            container.runs.fail(run_id, str(exc))

    try:
        container.executor.submit(_run_job)
    except Exception as exc:
        container.runs.fail(run_id, str(exc))
        raise HTTPException(status_code=500, detail=f"failed to submit task: {exc}") from exc

    return {"run_id": run_id, "status": "running"}


@router.get("/backtests")
def list_backtests(
    request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    container = _container(request)
    return {"items": container.runs.list(limit=limit)}


@router.get("/backtests/{run_id}")
def get_backtest(
    request: Request,
    run_id: str,
    include_trades: bool = Query(default=False),
    include_tables: bool = Query(default=False),
) -> dict[str, Any]:
    container = _container(request)
    item = container.runs.get(run_id, include_trades=include_trades, include_tables=include_tables)
    if item is None:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return item


@router.delete("/backtests/{run_id}")
def delete_backtest(request: Request, run_id: str) -> dict[str, Any]:
    container = _container(request)
    deleted = container.runs.delete(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return {"ok": True, "run_id": run_id}


@router.get("/backtests/{run_id}/equity")
def get_equity(request: Request, run_id: str) -> dict[str, Any]:
    container = _container(request)
    item = container.runs.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    result = item.get("result") or {}
    return {"run_id": run_id, "equity": result.get("equity", [])}


@router.get("/backtests/{run_id}/trades")
def get_trades(
    request: Request,
    run_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    format: str = Query(default="json"),
):
    container = _container(request)
    item = container.runs.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    result = item.get("result") or {}
    if format == "csv":
        csv_text = container.runner.to_trade_csv(result)
        return PlainTextResponse(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{run_id}_trades.csv"'},
        )
    return container.runner.get_trade_page(result=result, page=page, page_size=page_size)


@router.post("/ai/recommend")
def ai_recommend(request: Request, payload: AIRecommendRequest) -> dict[str, Any]:
    container = _container(request)
    result = container.ai.recommend(payload.model_dump())
    return result


@router.post("/ai/chat")
def ai_chat(request: Request, payload: AIChatRequest) -> dict[str, Any]:
    container = _container(request)
    result = container.ai.chat(payload.message, payload.current_config)
    return result


@router.post("/semantic/analyze")
def semantic_analyze(request: Request, payload: SemanticAnalyzeRequest) -> dict[str, Any]:
    container = _container(request)
    return container.semantic.analyze(payload.strategy_text)


@router.post("/system/shutdown")
def shutdown_service() -> dict[str, Any]:
    def _shutdown() -> None:
        time.sleep(0.2)
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()
    return {"ok": True, "message": "shutdown scheduled"}
