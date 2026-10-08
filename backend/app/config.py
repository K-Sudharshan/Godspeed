import os
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    supabase_url: str = Field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = Field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    
    # AI Config
    ai_provider: str = Field(default_factory=lambda: os.getenv("AI_PROVIDER", "gemini"))
    ai_api_key: str = Field(default_factory=lambda: os.getenv("AI_API_KEY", os.getenv("GEMINI_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("GROQ_API_KEY", "")))))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    groq_api_key: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    ai_model: str = Field(default_factory=lambda: os.getenv("AI_MODEL", "gemini-1.5-flash"))
    ai_timeout_ms: int = Field(default=15000)
    ai_max_retries: int = Field(default=1)
    
    # Risk policy thresholds
    approval_threshold: float = Field(default=500000.0)
    split_window_hours: int = Field(default=72)
    bank_change_lookback_days: int = Field(default=30)
    price_deviation_medium_threshold: float = Field(default=0.25)
    price_deviation_high_threshold: float = Field(default=0.40)
    
    port: int = Field(default=8000)
    host: str = Field(default="0.0.0.0")

    class Config:
        env_file = ".env"
        extra = "allow"

try:
    settings = Settings()
except Exception:
    # Fallback if pydantic-settings is not installed
    class SimpleSettings:
        def __init__(self):
            self.supabase_url = os.getenv("SUPABASE_URL", "")
            self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            self.ai_provider = os.getenv("AI_PROVIDER", "gemini")
            self.ai_api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or ""
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            self.groq_api_key = os.getenv("GROQ_API_KEY", "")
            self.ai_model = os.getenv("AI_MODEL", "gemini-1.5-flash")
            self.ai_timeout_ms = int(os.getenv("AI_TIMEOUT_MS", "15000"))
            self.ai_max_retries = int(os.getenv("AI_MAX_RETRIES", "1"))
            self.approval_threshold = float(os.getenv("APPROVAL_THRESHOLD", "500000.0"))
            self.split_window_hours = int(os.getenv("SPLIT_WINDOW_HOURS", "72"))
            self.bank_change_lookback_days = int(os.getenv("BANK_CHANGE_LOOKBACK_DAYS", "30"))
            self.price_deviation_medium_threshold = float(os.getenv("PRICE_DEVIATION_MEDIUM_THRESHOLD", "0.25"))
            self.price_deviation_high_threshold = float(os.getenv("PRICE_DEVIATION_HIGH_THRESHOLD", "0.40"))
            self.port = int(os.getenv("PORT", "8000"))
            self.host = os.getenv("HOST", "0.0.0.0")
    settings = SimpleSettings()
