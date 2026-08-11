from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.core.config import Settings


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    settings = Settings(
        _env_file=None,
        APP_DATA_DIR=tmp_path,
        DASHSCOPE_API_KEY=None,
        TAVILY_API_KEY=None,
    )
    try:
        from src.main import create_app
    except ImportError as exc:
        return _missing_app(str(exc))

    return create_app(data_dir=tmp_path, settings=settings)


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client


def _missing_app(reason: str) -> FastAPI:
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
    async def _not_implemented(path: str):
        return JSONResponse(
            {"detail": f"create_app 尚未实现或无法导入：{reason}"},
            status_code=501,
        )

    return app
