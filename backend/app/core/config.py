"""全局配置。所有环境相关的值只在这里出现一次。"""
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "小学学习工作台"
    ENV: str = "dev"
    SECRET_KEY: str = "dev-only-change-me"
    ACCESS_TOKEN_MIN: int = 30
    REFRESH_TOKEN_DAYS: int = 7

    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "study"
    MYSQL_PASSWORD: str = "change-me"
    MYSQL_DB: str = "study_table"

    DATA_ROOT: Path = Path.home() / "study_table_data"
    MAX_UPLOAD_MB: int = 60

    TIMEZONE: str = "Asia/Shanghai"
    SCHEDULER_ENABLED: bool = True

    @field_validator("DATA_ROOT")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return Path(v).expanduser().resolve()

    @property
    def database_url(self) -> str:
        pwd = quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{pwd}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @property
    def upload_dir(self) -> Path:
        return self.DATA_ROOT / "uploads"

    @property
    def backup_dir(self) -> Path:
        return self.DATA_ROOT / "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
