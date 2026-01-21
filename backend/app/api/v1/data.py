"""Data configuration API endpoints."""
from fastapi import APIRouter
from app.domain.data_config import DataConfig
from app.core.config import get_settings

router = APIRouter(prefix="/data", tags=["data"])

# In-memory config store (in production, use database or file)
_current_config: DataConfig | None = None


def get_current_config() -> DataConfig:
    """Get current data configuration, initializing from settings if needed."""
    global _current_config
    if _current_config is None:
        settings = get_settings()
        _current_config = DataConfig(
            htf_bars=settings.htf_bar_count,
            ltf_bars=settings.ltf_bar_count,
            micro_bars=settings.micro_bar_count,
            live_refresh_interval=settings.live_refresh_interval,
            data_mode=settings.data_mode,
        )
    return _current_config


@router.get("/config", response_model=DataConfig)
async def get_data_config() -> DataConfig:
    """Get current data configuration."""
    return get_current_config()


@router.put("/config", response_model=DataConfig)
async def update_data_config(config: DataConfig) -> DataConfig:
    """Update data configuration."""
    global _current_config
    _current_config = config
    return _current_config


@router.get("/modes")
async def get_available_modes() -> dict:
    """Get available data modes with descriptions."""
    return {
        "modes": [
            {"value": "SAMPLE", "label": "Sample", "description": "Generated synthetic data for development/testing"},
            {"value": "HISTORICAL", "label": "Historical", "description": "MT5 historical data fetch for one-time analysis"},
            {"value": "BACKTEST", "label": "Backtest", "description": "Simulated playback for strategy testing"},
            {"value": "LIVE", "label": "Live", "description": "Real-time MT5 stream for production trading"},
        ]
    }
