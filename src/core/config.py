from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "后端 MVP Agent"
    app_data_dir: Path = Field(default=Path("data"), alias="APP_DATA_DIR")
    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    llm_model_id: str = Field(default="qwen-plus", alias="LLM_MODEL_ID")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    tool_timeout_seconds: float = Field(default=180.0, alias="TOOL_TIMEOUT_SECONDS")
    circuit_breaker_failure_threshold: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    )

    @property
    def data_dir(self) -> Path:
        return self.app_data_dir

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "agent.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
