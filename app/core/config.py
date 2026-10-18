from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "Customized Learning Hub"
    env: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str
    database_url_sync: str

    # --- Sessions ---
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    session_cookie_name: str = "clh_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"

    # --- Password hashing ---
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 2

    # --- Token TTLs ---
    email_verification_ttl_seconds: int = 86400
    password_reset_ttl_seconds: int = 3600

    # --- OTP login ---
    login_otp_ttl_seconds: int = 600
    login_otp_max_attempts: int = 5
    login_otp_length: int = 8
    login_otp_return_code_in_response: bool = True

    # --- Business defaults ---
    default_subscription_price_usd: float = 25.0
    default_subscription_duration_days: int = 30
    default_notification_schedule: list[int] = Field(default_factory=lambda: [25, 20, 0])

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    # --- Payments ---
    momo_mock: bool = True
    momo_base_url: str = "https://sandbox.momodeveloper.mtn.com"
    momo_subscription_key: str = ""
    momo_api_user: str = ""
    momo_api_key: str = ""
    momo_target_environment: str = "sandbox"
    momo_callback_url: str = "http://localhost:8000/api/v1/payments/momo/webhook"
    momo_currency: str = "EUR"

    paypal_mock: bool = True
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_currency: str = "USD"

    # --- Email / SMTP ---
    # Field names mirror the KICS project so the same .env block works.
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "no-reply@clh.local"
    mail_from_name: str = "Customized Learning Hub"
    mail_server: str = ""
    mail_port: int = 587
    mail_starttls: bool = True
    mail_ssl_tls: bool = False
    mail_use_credentials: bool = True

    # If true, emails are logged to the console instead of sent.
    # Auto-disabled when MAIL_SERVER is set.
    email_mock: bool = True

    # --- Workers ---
    expiry_sweep_interval_seconds: int = 3600

    @field_validator("default_notification_schedule", mode="before")
    @classmethod
    def _parse_schedule(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def is_dev(self) -> bool:
        return self.env.lower() in ("development", "dev", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]