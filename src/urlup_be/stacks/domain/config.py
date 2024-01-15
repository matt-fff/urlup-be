import os

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SETTINGS_CONFIG = SettingsConfigDict(
    case_sensitive=False,
    env_file=os.environ.get("ENVFILE", ".env"),
    env_file_encoding="utf-8",
    env_nested_delimiter="__",
)


class DomainConfig(BaseModel):
    zone_domain: str
    cert_domain: str


class Config(BaseSettings):
    api_domain: DomainConfig = DomainConfig(
        zone_domain="urlup.org", cert_domain="api.urlup.org"
    )
    redirect_domain: DomainConfig = DomainConfig(
        zone_domain="uu1.ink", cert_domain="uu1.ink"
    )
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = SETTINGS_CONFIG
