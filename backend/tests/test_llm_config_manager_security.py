from app.services.llm_config_manager import LLMConfigManager


def test_llm_config_public_output_masks_api_key(tmp_path):
    config_file = tmp_path / "llm_config.json"
    manager = LLMConfigManager(config_file=config_file)
    manager.update(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "secret-key",
            "temperature": 0.2,
            "max_tokens": 1200,
            "enabled": True,
        }
    )
    public = manager.get_public()
    assert public["api_key"] == ""
    assert public["has_api_key"] is True


def test_llm_update_keeps_existing_api_key_when_blank(tmp_path):
    config_file = tmp_path / "llm_config.json"
    manager = LLMConfigManager(config_file=config_file)
    manager.update(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "secret-key",
            "temperature": 0.2,
            "max_tokens": 1200,
            "enabled": True,
        }
    )
    manager.update(
        {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "",
            "temperature": 0.3,
            "max_tokens": 800,
            "enabled": True,
        }
    )
    assert manager.get().api_key == "secret-key"
    assert manager.get().temperature == 0.3
    assert manager.get().max_tokens == 800

