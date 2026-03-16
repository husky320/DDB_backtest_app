from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.ai_skill_orchestrator import AISkillOrchestrator
from app.services.backtest_runner import BacktestRunner
from app.services.ddb_connection_manager import DolphinDBConnectionManager
from app.services.llm_config_manager import LLMConfigManager
from app.services.result_serializer import ResultSerializer
from app.services.run_store import BacktestRunStore
from app.services.semantic_strategy_service import SemanticStrategyService
from app.services.script_registry import DolphinDBScriptRegistry


@dataclass
class ServiceContainer:
    connection: DolphinDBConnectionManager
    registry: DolphinDBScriptRegistry
    serializer: ResultSerializer
    runner: BacktestRunner
    ai: AISkillOrchestrator
    runs: BacktestRunStore
    executor: ThreadPoolExecutor
    llm_config: LLMConfigManager
    semantic: SemanticStrategyService


def build_container() -> ServiceContainer:
    data_dir = settings.data_dir
    connection = DolphinDBConnectionManager(config_file=data_dir / "ddb_config.json")
    registry = DolphinDBScriptRegistry()
    serializer = ResultSerializer()
    runner = BacktestRunner(connection=connection, registry=registry, serializer=serializer)
    ai = AISkillOrchestrator()
    runs = BacktestRunStore(store_file=data_dir / "runs_store.json")
    executor = ThreadPoolExecutor(max_workers=settings.backtest_max_workers, thread_name_prefix="dolphindb-backtest")
    llm_config = LLMConfigManager(config_file=data_dir / "llm_config.json")
    semantic = SemanticStrategyService(llm_config_manager=llm_config, registry=registry)
    return ServiceContainer(
        connection=connection,
        registry=registry,
        serializer=serializer,
        runner=runner,
        ai=ai,
        runs=runs,
        executor=executor,
        llm_config=llm_config,
        semantic=semantic,
    )
