from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Kyron Take Home API"
    environment: str = "development"
    api_prefix: str = "/api"
    openai_api_key: str
    openai_realtime_model: str = "gpt-realtime"
    openai_voice_name: str = "alloy"
    openai_realtime_debug_greeting: bool = False
    openai_realtime_transport: str = "sip"
    openai_project_id: str | None = None
    openai_sip_uri: str | None = None
    openai_webhook_secret: str | None = None
    openai_webook_signing_secret: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    twilio_webhook_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @computed_field
    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @computed_field
    @property
    def openai_sip_configured(self) -> bool:
        return bool(self.openai_sip_uri or self.openai_project_id)

    @computed_field
    @property
    def openai_webhook_configured(self) -> bool:
        return bool(self.openai_webhook_secret or self.openai_webook_signing_secret)

    @computed_field
    @property
    def twilio_configured(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_phone_number
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
