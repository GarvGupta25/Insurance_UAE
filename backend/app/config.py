from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_anon_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_stt_model: str = "whisper-large-v3"
    send_real_emergency_alert: bool = False
    oncall_webhook_url: str = ""
    oncall_webhook_token: str = ""
    oncall_response_target_minutes: int = 15
    claim_confidence_threshold: float = 0.6
    claim_duplicate_threshold: float = 0.8
    claim_auto_approve_cap_aed: int = 10000
    document_encryption_key: str = ""
    payment_provider: str = "simulator"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    tesseract_cmd: str = ""


@lru_cache
def settings():
    return Settings()
