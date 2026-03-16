from pathlib import Path

from app.services.script_registry import DolphinDBScriptRegistry


def test_discover_script_root_prefers_env_override(tmp_path, monkeypatch):
    env_root = tmp_path / "custom_scripts"
    env_root.mkdir(parents=True)
    monkeypatch.setenv("DOLPHINDB_SCRIPT_ROOT", str(env_root))

    registry = DolphinDBScriptRegistry(script_root=tmp_path)

    assert registry._discover_script_root(tmp_path / "project_root") == env_root


def test_discover_script_root_finds_sibling_cygg_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("DOLPHINDB_SCRIPT_ROOT", raising=False)
    project_root = tmp_path / "DDB_backtest_app_prod"
    project_root.mkdir()
    sibling_scripts = tmp_path / "CYGG" / "DDB_BT"
    sibling_scripts.mkdir(parents=True)

    registry = DolphinDBScriptRegistry(script_root=tmp_path)

    assert registry._discover_script_root(project_root) == sibling_scripts
