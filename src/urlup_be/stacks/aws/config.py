import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SETTINGS_CONFIG = SettingsConfigDict(
    case_sensitive=False,
    env_file=os.environ.get("ENVFILE", ".env"),
    env_file_encoding="utf-8",
    env_nested_delimiter="__",
)


class Config(BaseSettings):
    env: str = "dev"
    domain_stack_name: str = "codefold/urlup-domain/dev"
    table_name: str = "urlup"
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = SETTINGS_CONFIG
