from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppSettings:
    app_name: str = "DolphinDB Backtest App"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/dolphindb"
    cors_origins: tuple[str, ...] = ("*",)
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    backtest_max_workers: int = 4

    @classmethod
    def from_env(cls) -> "AppSettings":
        app_name = os.getenv("DOLPHINDB_APP_NAME", "DolphinDB Backtest App")
        app_version = os.getenv("DOLPHINDB_APP_VERSION", "0.1.0")
        api_prefix = os.getenv("DOLPHINDB_API_PREFIX", "/api/dolphindb")
        cors_raw = os.getenv("DOLPHINDB_CORS_ORIGINS", "*")
        max_workers = int(os.getenv("DOLPHINDB_BACKTEST_MAX_WORKERS", "4"))
        cors_origins = tuple(part.strip() for part in cors_raw.split(",") if part.strip()) or ("*",)
        return cls(
            app_name=app_name,
            app_version=app_version,
            api_prefix=api_prefix,
            cors_origins=cors_origins,
            backtest_max_workers=max(1, max_workers),
        )


settings = AppSettings.from_env()
settings.data_dir.mkdir(parents=True, exist_ok=True)
