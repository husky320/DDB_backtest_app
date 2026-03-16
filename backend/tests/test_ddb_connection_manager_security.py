import pytest

from app.services.ddb_connection_manager import DDBConfig, DDBNodeStatus, DolphinDBConnectionManager


def test_public_config_masks_password():
    cfg = DDBConfig(password="abc123")
    public = cfg.to_public_dict()
    assert public["password"] == ""
    assert public["has_password"] is True


def test_update_config_keeps_existing_password_when_blank(tmp_path):
    manager = DolphinDBConnectionManager(config_file=tmp_path / "ddb_config.json")
    manager.update_config(
        {
            "host": "127.0.0.1",
            "port": 8030,
            "username": "admin",
            "password": "secret-password",
            "candidate_ports": [8030],
            "preferred_data_node": "",
        },
        validate_connection=False,
    )
    manager.update_config(
        {
            "host": "127.0.0.1",
            "port": 8031,
            "username": "admin",
            "password": "",
            "candidate_ports": [8031],
            "preferred_data_node": "",
        },
        validate_connection=False,
    )
    assert manager.get_config().password == "secret-password"
    assert manager.get_config().port == 8031


def test_update_config_rolls_back_when_no_usable_node(tmp_path, monkeypatch):
    manager = DolphinDBConnectionManager(config_file=tmp_path / "ddb_config.json")
    original_host = manager.get_config().host

    def fake_probe(force: bool = False):
        return [DDBNodeStatus(host="127.0.0.1", port=1, available=False, can_load_dfs=False, error="unreachable")]

    monkeypatch.setattr(manager, "probe_data_nodes", fake_probe)
    with pytest.raises(RuntimeError, match="No available DolphinDB data node"):
        manager.update_config(
            {
                "host": "127.0.0.1",
                "port": 1,
                "username": "admin",
                "password": "123456",
                "candidate_ports": [1],
                "preferred_data_node": "",
            },
            validate_connection=True,
        )
    assert manager.get_config().host == original_host

