from app.services.run_store import BacktestRunStore


def test_run_store_persists_and_recovers_runs(tmp_path):
    store_file = tmp_path / "runs_store.json"
    store = BacktestRunStore(store_file=store_file)
    store.create(
        "run-1",
        "combo_01",
        {
            "template_id": "combo_01",
            "user_config": {
                "buyFactors": ["total_mv", "ma5"],
                "sellFactors": ["macdDeadCross"],
            },
        },
    )
    store.complete(
        "run-1",
        {
            "degraded": True,
            "execution": {"duration_ms": 123.0},
            "kpis": {"totalReturn": 0.1},
        },
    )

    recovered = BacktestRunStore(store_file=store_file)
    item = recovered.get("run-1")
    assert item is not None
    assert item["status"] == "degraded"
    assert item["duration_ms"] == 123.0
    assert item["result"]["kpis"]["totalReturn"] == 0.1
    assert "总市值" in item["strategy_label"]


def test_run_store_formats_error_info(tmp_path):
    store_file = tmp_path / "runs_store.json"
    store = BacktestRunStore(store_file=store_file)
    store.create("run-2", "combo_01", {"template_id": "combo_01"})
    store.fail("run-2", "startDate must be earlier than or equal to endDate.")
    item = store.get("run-2")
    assert item is not None
    assert item["status"] == "failed"
    assert item["error_info"]["code"] == "config.date_order"
    assert "开始日期不能晚于结束日期" in item["error"]
    assert "startDate must be earlier" in item["error_detail"]


def test_run_store_delete_removes_item(tmp_path):
    store_file = tmp_path / "runs_store.json"
    store = BacktestRunStore(store_file=store_file)
    store.create("run-3", "combo_01", {"template_id": "combo_01"})
    assert store.delete("run-3") is True
    assert store.get("run-3") is None
    assert store.delete("run-3") is False


def test_run_store_compacts_tables_and_can_hide_trades(tmp_path):
    store_file = tmp_path / "runs_store.json"
    store = BacktestRunStore(store_file=store_file)
    store.create("run-4", "combo_01", {"template_id": "combo_01"})
    store.complete(
        "run-4",
        {
            "degraded": False,
            "trades": [{"symbol": "000001.SZ", "side": "BUY"}],
            "tables": {"dailyTotalPortfolios": [{"tradeDate": "2026-03-16"}]},
        },
    )

    recovered = BacktestRunStore(store_file=store_file)
    full_item = recovered.get("run-4")
    assert full_item is not None
    assert full_item["result"]["tables"] == {}
    assert len(full_item["result"]["trades"]) == 1

    light_item = recovered.get("run-4", include_trades=False)
    assert light_item is not None
    assert light_item["result"]["trades"] == []


def test_run_store_sanitizes_legacy_rows_on_load(tmp_path):
    store_file = tmp_path / "runs_store.json"
    store_file.write_text(
        """
{
  "runs": [
    {
      "run_id": "run-legacy",
      "template_id": "combo_01",
      "status": "completed",
      "request": {"template_id": "combo_01"},
      "created_at": "2026-03-16T10:00:00Z",
      "result": {
        "trades": [{"symbol": "000001.SZ"}],
        "tables": {"tradeDetails": [{"symbol": "000001.SZ"}]}
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    recovered = BacktestRunStore(store_file=store_file)
    item = recovered.get("run-legacy")
    assert item is not None
    assert item["result"]["tables"] == {}
    assert '"tables": {}' in store_file.read_text(encoding="utf-8")
