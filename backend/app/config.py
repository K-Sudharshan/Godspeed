import os
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = ConfigDict(extra="allow", env_file=".env")

    supabase_url: str = Field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = Field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    
    # AI Config
    ai_provider: str = Field(default_factory=lambda: os.getenv("AI_PROVIDER", "groq"))
    groq_api_key: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = Field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    ai_api_key: str = Field(default_factory=lambda: os.getenv("AI_API_KEY", ""))
    ai_model: str = Field(default_factory=lambda: os.getenv("AI_MODEL", "openai/gpt-oss-120b"))
    ai_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("AI_TIMEOUT_SECONDS", os.getenv("AI_TIMEOUT_MS", "15000")) if int(os.getenv("AI_TIMEOUT_SECONDS", "0")) > 0 else int(int(os.getenv("AI_TIMEOUT_MS", "15000")) / 1000)))
    ai_timeout_ms: int = Field(default=15000)
    ai_max_retries: int = Field(default_factory=lambda: int(os.getenv("AI_MAX_RETRIES", "1")))
    
    # Risk policy thresholds
    approval_threshold: float = Field(default=500000.0)
    split_window_hours: int = Field(default=72)
    bank_change_lookback_days: int = Field(default=30)
    price_deviation_medium_threshold: float = Field(default=0.25)
    price_deviation_high_threshold: float = Field(default=0.40)
    
    port: int = Field(default=8000)
    host: str = Field(default="0.0.0.0")

try:
    settings = Settings()
except Exception:
    class SimpleSettings:
        def __init__(self):
            self.supabase_url = os.getenv("SUPABASE_URL", "")
            self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            self.ai_provider = os.getenv("AI_PROVIDER", "groq")
            self.groq_api_key = os.getenv("GROQ_API_KEY", "")
            self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
            self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            self.ai_api_key = os.getenv("AI_API_KEY", "")
            self.ai_model = os.getenv("AI_MODEL", "openai/gpt-oss-120b")
            timeout_sec = int(os.getenv("AI_TIMEOUT_SECONDS", "15"))
            self.ai_timeout_seconds = timeout_sec
            self.ai_timeout_ms = timeout_sec * 1000
            self.ai_max_retries = int(os.getenv("AI_MAX_RETRIES", "1"))
            self.approval_threshold = float(os.getenv("APPROVAL_THRESHOLD", "500000.0"))
            self.split_window_hours = int(os.getenv("SPLIT_WINDOW_HOURS", "72"))
            self.bank_change_lookback_days = int(os.getenv("BANK_CHANGE_LOOKBACK_DAYS", "30"))
            self.price_deviation_medium_threshold = float(os.getenv("PRICE_DEVIATION_MEDIUM_THRESHOLD", "0.25"))
            self.price_deviation_high_threshold = float(os.getenv("PRICE_DEVIATION_HIGH_THRESHOLD", "0.40"))
            self.port = int(os.getenv("PORT", "8000"))
            self.host = os.getenv("HOST", "0.0.0.0")
    settings = SimpleSettings()

