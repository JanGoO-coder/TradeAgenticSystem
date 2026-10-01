"""Application configuration settings."""
from pydantic_settings import BaseSettings
from typing import Literal
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
    mt5_terminal_path: str | None = None

    # =========================================================================
    # LLM Configuration (LM Studio local API)
    # =========================================================================
    lmstudio_base_url: str = "http://localhost:1234"
    lmstudio_api_token: str | None = None
    lmstudio_model: str = "google/gemma-4-e2b"
    lmstudio_context_length: int | None = None
    lmstudio_reasoning: Literal["off", "low", "medium", "high", "on"] | None = None
    lmstudio_auto_load_model: bool = True

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

    # =========================================================================
    # Agentic Hub Configuration
    # =========================================================================
    hub_enabled: bool = True
    hub_rr_minimum: float = 3.0
    hub_risk_per_trade_pct: float = 0.5
    hub_risk_cap_pct: float = 1.0
    hub_daily_loss_limit_pct: float = 4.0
    hub_total_drawdown_limit_pct: float = 8.0
    hub_max_concurrent_trades: int = 2
    hub_killzone_london_start_utc: str = "02:00"
    hub_killzone_london_end_utc: str = "05:00"
    hub_killzone_ny_start_utc: str = "07:00"
    hub_killzone_ny_end_utc: str = "10:00"
    hub_profit_target_pct: float = 10.0
    hub_scale_down_threshold_pct: float = 2.0

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
