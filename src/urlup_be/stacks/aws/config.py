import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SETTINGS_CONFIG = SettingsConfigDict(
    case_sensitive=False,
    env_file=os.environ.get("ENVFILE", ".env"),
    env_file_encoding="utf-8",
    env_nested_delimiter="__",
)


class UsageLimits(BaseModel):
    period_limit: int = 3000
    period_type: str = "DAY"
    rate_limit: int = 60
    burst_limit: int = 300


class Config(BaseSettings):
    env: str = "dev"
    domain_stack_name: str = "codefold/urlup-domain/dev"
    table_name: str = "urlup"
    tags: dict[str, str] = Field(default_factory=dict)
    usage: UsageLimits = Field(default_factory=UsageLimits)

    model_config = SETTINGS_CONFIG
