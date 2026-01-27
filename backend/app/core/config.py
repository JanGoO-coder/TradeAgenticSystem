"""Application configuration settings."""
from pydantic_settings import BaseSettings
from typing import Optional, List
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

    # Mode Settings (ANALYSIS_ONLY, SIMULATION, APPROVAL_REQUIRED, EXECUTION)
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

    # ==================== DATA STORAGE ====================
    data_dir: str = "./data"                      # Base data directory
    tick_cache_dir: str = "./data/tick_cache"     # Cached tick data (hourly chunks)
    sessions_dir: str = "./data/sessions"         # Saved backtest sessions

    # Tick replay settings
    tick_buffer_hours: int = 3                    # Max hours of tick data loaded (prev/current/next)
    tick_chunk_max_mb: float = 50.0               # Memory limit for tick buffer (~50MB)

    # ==================== RISK MANAGEMENT ====================
    # Position sizing
    max_lot_size: float = 1.0           # Maximum lot size per trade
    min_lot_size: float = 0.01          # Minimum lot size

    # Daily limits
    max_daily_loss_pct: float = 5.0     # Max daily drawdown percentage
    max_daily_profit_pct: float = 10.0  # Max daily profit (for overtrading prevention)
    max_trades_per_day: int = 10        # Maximum trades per day

    # Concurrent position limits
    max_open_positions: int = 5         # Max concurrent positions
    max_positions_per_symbol: int = 2   # Max positions per symbol
    max_total_exposure_pct: float = 20.0  # Max total margin usage percentage

    # ==================== TRADE REQUIREMENTS ====================
    require_stop_loss: bool = True      # SL mandatory for all trades
    require_take_profit: bool = False   # TP optional by default
    min_rr_ratio: float = 2.0           # Minimum risk-reward ratio
    max_stop_loss_pct: float = 2.0      # Max SL as percentage of account
    min_stop_loss_pips: float = 5.0     # Minimum SL distance in pips

    # ==================== SYMBOL RESTRICTIONS ====================
    allowed_symbols: List[str] = []     # Empty = all symbols allowed
    blocked_symbols: List[str] = []     # Symbols to block (higher priority)

    # ==================== SAFETY GUARDRAILS ====================
    emergency_stop: bool = False        # Global kill switch - blocks ALL trading
    paper_trade_first: bool = True      # Require SIMULATION before EXECUTION
    min_simulation_trades: int = 5      # Min simulated trades before going live

    # Confirmation requirements
    require_trade_confirmation: bool = True    # UI must confirm before execution
    confirmation_delay_seconds: int = 5        # Countdown before execute button enables
    double_confirm_large_trades: bool = True   # Extra confirmation for large positions
    large_trade_threshold_lots: float = 0.5    # What counts as "large"

    # Approval mode settings
    approval_timeout_seconds: int = 60   # Auto-reject if not approved in time
    auto_reject_on_timeout: bool = True  # Whether to reject or just expire

    # ==================== AUDIT & LOGGING ====================
    log_all_trade_attempts: bool = True   # Log even failed/blocked attempts
    log_position_changes: bool = True     # Log every SL/TP modification
    screenshot_on_trade: bool = False     # Take chart screenshot on trade

    # Daily loss tracking reset time (UTC hour)
    daily_reset_hour: int = 0             # Midnight UTC

    # ==================== ERROR HANDLING ====================
    max_retry_attempts: int = 3           # Retries for failed orders
    retry_delay_ms: int = 500             # Delay between retries
    requote_tolerance_pips: float = 2.0   # Accept requotes within this range

    # External APIs
    google_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
