from app.services.ai_skill_orchestrator import AISkillOrchestrator


def test_chat_generates_patch_for_supported_actions():
    orchestrator = AISkillOrchestrator()
    result = orchestrator.chat("把回测区间改成 2023-01-01 到 2023-12-31，最大持股数调到10，并回测", {})
    assert result["blocked"] is False
    assert result["config_patch"]["startDate"] == "2023.01.01"
    assert result["config_patch"]["endDate"] == "2023.12.31"
    assert result["config_patch"]["maxPositionLimit"] == 10
    assert result["trigger_run"] is True


def test_chat_blocks_out_of_scope_request():
    orchestrator = AISkillOrchestrator()
    result = orchestrator.chat("请帮我做实盘下单并自动交易", {})
    assert result["blocked"] is True
    assert "超出当前回测产品范围" in result["reason"]


def test_chat_blocks_out_of_scope_request_with_variant_phrase():
    orchestrator = AISkillOrchestrator()
    result = orchestrator.chat("可以帮我做实盘自动下单吗？", {})
    assert result["blocked"] is True
    assert "超出当前回测产品范围" in result["reason"]


def test_recommend_strategy_ideas_returns_summary_and_examples():
    orchestrator = AISkillOrchestrator()
    result = orchestrator.recommend(
        {
            "mode": "strategy_ideas",
            "template_id": "combo_01",
            "current_config": {"benchmark": "000300.SH", "holdingPeriod": 60},
            "backtest_tasks": [
                {
                    "run_id": "run-001",
                    "template_id": "combo_01",
                    "request": {
                        "user_config": {
                            "factorCustomization": {
                                "buy": {
                                    "logic": "and",
                                    "fundamentals": [{"field": "total_mv", "op": ">=", "value": 20000000, "enabled": True}],
                                    "technicals": [{"type": "ma_above", "period": 5, "enabled": True}],
                                },
                                "sell": {
                                    "logic": "and",
                                    "fundamentals": [],
                                    "technicals": [{"type": "macd_dead", "enabled": True}],
                                },
                            },
                            "holdingPeriod": 60,
                            "benchmark": "000300.SH",
                        }
                    },
                    "result": {"kpis": {"totalReturn": 0.25, "maxDrawdown": 0.08, "sharpeRatio": 1.6}},
                }
            ],
        }
    )
    assert "summary" in result
    assert result["summary"]["completed_count"] == 1
    assert result["enhancement_examples"]
    assert result["enhancement_examples"][0].startswith("示例：")
    assert result["diversified_examples"]
