from pathlib import Path

from src.core.config import Settings


def test_settings_loads_env_values(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dash-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "qwen-plus")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    settings = Settings(_env_file=None)

    assert settings.dashscope_api_key == "dash-key"
    assert settings.dashscope_base_url == "https://example.test/compatible-mode/v1"
    assert settings.llm_model_id == "qwen-plus"
    assert settings.tavily_api_key == "tavily-key"
    assert settings.data_dir == tmp_path
    assert settings.sqlite_path == tmp_path / "agent.sqlite3"
    assert settings.tool_timeout_seconds == 180
    assert settings.circuit_breaker_failure_threshold == 3
