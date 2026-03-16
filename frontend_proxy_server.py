from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"
BACKEND_BASE = "http://127.0.0.1:8000"

app = FastAPI(title="DDB Frontend Proxy")
if ASSETS_DIR.exists():
  app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.api_route(
  "/api/{full_path:path}",
  methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_api(full_path: str, request: Request) -> Response:
  target_url = f"{BACKEND_BASE}/api/{full_path}"
  headers = dict(request.headers)
  headers.pop("host", None)
  body = await request.body()
  # Do not inherit system proxy env vars for localhost internal hop.
  async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
    resp = await client.request(
      method=request.method,
      url=target_url,
      params=request.query_params,
      headers=headers,
      content=body,
    )
  return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))


@app.get("/{path:path}")
async def serve_spa(path: str) -> Response:
  if not DIST_DIR.exists():
    return PlainTextResponse("frontend dist not found. Build frontend first.", status_code=500)
  requested = (DIST_DIR / path).resolve()
  if path and requested.exists() and requested.is_file() and DIST_DIR in requested.parents:
    return FileResponse(requested)
  index = DIST_DIR / "index.html"
  if not index.exists():
    return PlainTextResponse("index.html not found in dist.", status_code=500)
  return FileResponse(index)
