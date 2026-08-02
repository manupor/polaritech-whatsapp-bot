from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # WhatsApp Cloud API
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    meta_api_version: str = "v21.0"

    # OpenAI (future use)
    openai_api_key: str = ""

    # App
    app_env: str = "development"
    log_level: str = "info"

    # Escalation
    escalation_phone_number: str = ""

    # Outbound HTTP
    whatsapp_send_timeout: float = 30.0

    # Database
    database_url: str = "sqlite:///polaritech.db"

    # Welcome flow
    whatsapp_welcome_image_url: str = ""
    whatsapp_welcome_image_id: str = ""
    welcome_window_hours: float = 24.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_staging(self) -> bool:
        return self.app_env == "staging"

    @property
    def whatsapp_api_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.meta_api_version}"
            f"/{self.whatsapp_phone_number_id}/messages"
        )


settings = Settings()
