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

    # LLM Provider (openai or anthropic)
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o-mini"  # or claude-3-haiku for Anthropic
    llm_temperature: float = 0.3  # Low temperature for consistent responses
    llm_max_tokens: int = 500

    # App
    app_env: str = "development"
    log_level: str = "info"

    # Escalation
    escalation_phone_number: str = ""

    # Outbound HTTP
    whatsapp_send_timeout: float = 60.0

    # Database
    database_url: str = "sqlite:///polaritech.db"

    # Welcome flow
    whatsapp_welcome_image_url: str = ""
    whatsapp_welcome_image_id: str = ""
    welcome_window_hours: float = 24.0

    # Deployment / public URL (Vercel sets this automatically)
    vercel_url: str = ""
    app_url: str = ""

    @property
    def public_url(self) -> str:
        """Return the public URL for this deployment."""
        if self.app_url:
            return self.app_url.rstrip("/")
        if self.vercel_url:
            return f"https://{self.vercel_url.rstrip('/')}"
        return ""

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
