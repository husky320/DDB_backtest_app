from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import requests
from playwright.sync_api import sync_playwright


BASE_API = "http://127.0.0.1:8000/api/dolphindb"
BASE_WEB = "http://localhost:5173"
OUT_DIR = Path("runtime/docs/screenshots")


def get_latest_run_id() -> Optional[str]:
  try:
    resp = requests.get(f"{BASE_API}/backtests", params={"limit": 20}, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
      return None
    return items[0].get("run_id")
  except Exception:
    return None


def capture() -> None:
  OUT_DIR.mkdir(parents=True, exist_ok=True)
  run_id = get_latest_run_id()

  with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 980})

    page.goto(f"{BASE_WEB}/factors", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT_DIR / "01_factor_page_full.png"), full_page=True)

    # Toggle one fundamental + one technical factor to expose condition settings.
    basic_card = page.locator(".card").nth(2)
    tech_card = page.locator(".card").nth(3)
    if basic_card.locator(".chip").count() > 0:
      basic_card.locator(".chip").first.click()
      page.wait_for_timeout(250)
    if tech_card.locator(".chip").count() > 0:
      tech_card.locator(".chip").first.click()
      page.wait_for_timeout(250)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.45)")
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT_DIR / "02_factor_conditions.png"), full_page=True)

    page.goto(f"{BASE_WEB}/backtest", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT_DIR / "03_backtest_page_full.png"), full_page=True)

    page.goto(f"{BASE_WEB}/tasks", wait_until="networkidle")
    page.wait_for_timeout(1600)
    page.screenshot(path=str(OUT_DIR / "04_tasks_page_list.png"), full_page=True)

    if run_id:
      page.goto(f"{BASE_WEB}/tasks?run_id={run_id}", wait_until="networkidle")
      page.wait_for_timeout(2200)
      page.screenshot(path=str(OUT_DIR / "05_task_result_overview.png"), full_page=False)
      page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.58)")
      page.wait_for_timeout(1000)
      page.screenshot(path=str(OUT_DIR / "06_task_result_code.png"), full_page=False)

    page.goto(f"{BASE_WEB}/settings", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT_DIR / "07_settings_page_full.png"), full_page=True)

    browser.close()

  meta = {
    "base_web": BASE_WEB,
    "base_api": BASE_API,
    "run_id": run_id,
    "screenshots": sorted([p.name for p in OUT_DIR.glob("*.png")]),
  }
  (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
  capture()
