"""Application configuration settings."""
from pydantic_settings import BaseSettings
from typing import Optional, Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    api_v1_prefix: str = "/api/v1"
    project_name: str = "ICT Trading Platform"
    debug: bool = True

    # CORS Settings
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

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
    data_mode: str = "HISTORICAL"  # HISTORICAL, BACKTEST, LIVE (MT5 only)

    # MT5 Configuration (optional)
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None

    # =========================================================================
    # LLM Configuration
    # =========================================================================
    # Groq
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    
    # DeepSeek (uses OpenAI-compatible API)
    # Models: deepseek-chat (fast), deepseek-reasoner (thinking/complex reasoning)
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    
    # Legacy Gemini settings (for embeddings)
    gemini_api_key: str | None = None
    google_api_key: str | None = None  # Alternative name for gemini_api_key
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # Rate limiting
    llm_rpm_limit: int = 1500          # Requests per minute
    llm_burst_size: int = 25           # Max concurrent requests
    llm_retry_attempts: int = 3        # Retry on 429 errors

    # Reasoning mode: "verbose" for UI (chain-of-thought), "concise" for batch
    reasoning_mode: Literal["verbose", "concise"] = "verbose"

    # =========================================================================
    # ChromaDB Vector Store Configuration
    # =========================================================================
    chroma_host: str = "localhost"
    chroma_port: int = 8002

    # Strategy indexing
    strategies_dir: str = "../rules"         # Directory to scan for .md files (relative to backend)
    strategy_collection: str = "strategies"

    # =========================================================================
    # Backtesting Configuration
    # =========================================================================
    backtest_max_concurrent: int = 10     # Max parallel agent calls
    backtest_selective_mode: bool = True  # Only analyze on state changes
    backtest_sessions_dir: str = "data/sessions"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
