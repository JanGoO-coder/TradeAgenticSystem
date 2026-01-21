"""Data configuration models."""
from pydantic import BaseModel, Field
from typing import List


class DataConfig(BaseModel):
    """Configuration for data fetching and display."""
    
    htf_bars: int = Field(default=50, ge=10, le=500, description="1H candles count (default 50 = ~2 days)")
    ltf_bars: int = Field(default=100, ge=10, le=500, description="15M candles count (default 100 = ~25 hours)")
    micro_bars: int = Field(default=50, ge=10, le=500, description="5M candles count (default 50 = ~4 hours)")
    timeframes: List[str] = Field(default=["1H", "15M", "5M"], description="Timeframes to fetch")
    live_refresh_interval: int = Field(default=60, ge=10, le=300, description="Live mode refresh interval in seconds")
    data_mode: str = Field(default="SAMPLE", description="Data mode: SAMPLE, HISTORICAL, BACKTEST, LIVE")
    
    class Config:
        json_schema_extra = {
            "example": {
                "htf_bars": 50,
                "ltf_bars": 100,
                "micro_bars": 50,
                "timeframes": ["1H", "15M", "5M"],
                "live_refresh_interval": 60,
                "data_mode": "SAMPLE"
            }
        }
