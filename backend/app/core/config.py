"""Application configuration settings."""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Settings
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ICT Trading Platform"
    debug: bool = True
    
    # CORS Settings
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Agent Settings
    default_risk_pct: float = 1.0
    default_rr_minimum: float = 2.0
    max_trades_per_session: int = 3
    
    # Mode Settings (ANALYSIS_ONLY, SIMULATION, EXECUTION)
    execution_mode: str = "ANALYSIS_ONLY"
    
    # Timezone (for session detection)
    timezone: str = "America/New_York"
    
    # Data Configuration
    htf_bar_count: int = 50       # 1H candles
    ltf_bar_count: int = 100      # 15M candles
    micro_bar_count: int = 50     # 5M candles
    live_refresh_interval: int = 60  # seconds
    data_mode: str = "SAMPLE"     # SAMPLE, HISTORICAL, BACKTEST, LIVE
    
    # MT5 Configuration (optional)
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
