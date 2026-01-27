"""
ICT Agentic Trading System - Main Entry Point

This system implements the ICT Rulebook V1 using the hierarchical agent architecture.
It does NOT execute trades - only produces Trade Setup Responses.
"""
import json
from datetime import datetime

from src.main_agent import MainAgent
from src.rules_config import load_rules, PROJECT_ROOT


def create_sample_snapshot() -> dict:
    """
    Create a hypothetical market snapshot for EURUSD.
    This simulates a bullish ICT 2022 setup during NY Kill Zone.
    Timestamp: 9:00 AM EST (14:00 UTC) - Within NY Kill Zone (7-10 AM EST)
    """
    # Generate hypothetical 1H candles showing clear bullish structure (HH/HL)
    candles_1h = [
        # Initial swing low
        {"timestamp": "2026-01-20T06:00:00Z", "open": 1.0800, "high": 1.0820, "low": 1.0790, "close": 1.0810, "volume": 1000},
        {"timestamp": "2026-01-20T07:00:00Z", "open": 1.0810, "high": 1.0830, "low": 1.0795, "close": 1.0825, "volume": 1100},
        {"timestamp": "2026-01-20T08:00:00Z", "open": 1.0825, "high": 1.0850, "low": 1.0820, "close": 1.0845, "volume": 1200},
        # First swing high
        {"timestamp": "2026-01-20T09:00:00Z", "open": 1.0845, "high": 1.0880, "low": 1.0840, "close": 1.0870, "volume": 1500},
        {"timestamp": "2026-01-20T10:00:00Z", "open": 1.0870, "high": 1.0885, "low": 1.0860, "close": 1.0875, "volume": 1300},
        {"timestamp": "2026-01-20T11:00:00Z", "open": 1.0875, "high": 1.0890, "low": 1.0865, "close": 1.0880, "volume": 1200},
        # Pullback to higher low
        {"timestamp": "2026-01-20T12:00:00Z", "open": 1.0880, "high": 1.0885, "low": 1.0850, "close": 1.0855, "volume": 1400},
        {"timestamp": "2026-01-20T13:00:00Z", "open": 1.0855, "high": 1.0860, "low": 1.0830, "close": 1.0840, "volume": 1350},
        {"timestamp": "2026-01-20T14:00:00Z", "open": 1.0840, "high": 1.0855, "low": 1.0825, "close": 1.0850, "volume": 1300},
        # Second swing low (Higher Low - above 1.0790)
        {"timestamp": "2026-01-20T15:00:00Z", "open": 1.0850, "high": 1.0860, "low": 1.0835, "close": 1.0858, "volume": 1250},
        {"timestamp": "2026-01-20T16:00:00Z", "open": 1.0858, "high": 1.0875, "low": 1.0855, "close": 1.0872, "volume": 1200},
        # Rally to new swing high
        {"timestamp": "2026-01-20T17:00:00Z", "open": 1.0872, "high": 1.0900, "low": 1.0868, "close": 1.0895, "volume": 1600},
        {"timestamp": "2026-01-20T18:00:00Z", "open": 1.0895, "high": 1.0920, "low": 1.0890, "close": 1.0915, "volume": 1700},
        # Second swing high (Higher High - above 1.0890)
        {"timestamp": "2026-01-20T19:00:00Z", "open": 1.0915, "high": 1.0950, "low": 1.0910, "close": 1.0940, "volume": 1800},
        {"timestamp": "2026-01-20T20:00:00Z", "open": 1.0940, "high": 1.0960, "low": 1.0935, "close": 1.0955, "volume": 1750},
        {"timestamp": "2026-01-20T21:00:00Z", "open": 1.0955, "high": 1.0965, "low": 1.0945, "close": 1.0960, "volume": 1500},
        # Continuation
        {"timestamp": "2026-01-21T08:00:00Z", "open": 1.0960, "high": 1.0985, "low": 1.0955, "close": 1.0980, "volume": 1600},
        {"timestamp": "2026-01-21T09:00:00Z", "open": 1.0980, "high": 1.1010, "low": 1.0975, "close": 1.1005, "volume": 1800},
        {"timestamp": "2026-01-21T10:00:00Z", "open": 1.1005, "high": 1.1030, "low": 1.0995, "close": 1.1025, "volume": 1900},
        {"timestamp": "2026-01-21T11:00:00Z", "open": 1.1025, "high": 1.1050, "low": 1.1015, "close": 1.1045, "volume": 2000},
    ]
    
    # Generate 15M candles with clear bullish structure, sell-side sweep and FVG
    # Structure: Low1 (1.1015) -> High1 (1.1050) -> Low2 (1.1025, HL) -> High2 (1.1120, HH)
    candles_15m = [
        # Initial rally
        {"timestamp": "2026-01-21T10:00:00Z", "open": 1.1000, "high": 1.1020, "low": 1.0995, "close": 1.1018, "volume": 500},
        {"timestamp": "2026-01-21T10:15:00Z", "open": 1.1018, "high": 1.1030, "low": 1.1015, "close": 1.1028, "volume": 550},
        # Swing Low 1
        {"timestamp": "2026-01-21T10:30:00Z", "open": 1.1028, "high": 1.1032, "low": 1.1012, "close": 1.1015, "volume": 600},
        {"timestamp": "2026-01-21T10:45:00Z", "open": 1.1015, "high": 1.1035, "low": 1.1010, "close": 1.1030, "volume": 700},
        {"timestamp": "2026-01-21T11:00:00Z", "open": 1.1030, "high": 1.1045, "low": 1.1025, "close": 1.1042, "volume": 750},
        # Swing High 1
        {"timestamp": "2026-01-21T11:15:00Z", "open": 1.1042, "high": 1.1055, "low": 1.1038, "close": 1.1050, "volume": 680},
        {"timestamp": "2026-01-21T11:30:00Z", "open": 1.1050, "high": 1.1058, "low": 1.1045, "close": 1.1048, "volume": 650},
        # Pullback to Swing Low 2 (Higher Low - sweeps sell-side)
        {"timestamp": "2026-01-21T11:45:00Z", "open": 1.1048, "high": 1.1052, "low": 1.1030, "close": 1.1035, "volume": 700},
        {"timestamp": "2026-01-21T12:00:00Z", "open": 1.1035, "high": 1.1040, "low": 1.1020, "close": 1.1025, "volume": 750},
        # Sweep of sell-side liquidity below 1.1020 + rejection
        {"timestamp": "2026-01-21T12:15:00Z", "open": 1.1025, "high": 1.1030, "low": 1.1008, "close": 1.1028, "volume": 900},
        # DISPLACEMENT candle creating FVG (big bullish candle)
        {"timestamp": "2026-01-21T12:30:00Z", "open": 1.1028, "high": 1.1075, "low": 1.1025, "close": 1.1070, "volume": 1200},
        # Rally to Swing High 2 (Higher High)
        {"timestamp": "2026-01-21T12:45:00Z", "open": 1.1070, "high": 1.1095, "low": 1.1065, "close": 1.1090, "volume": 900},
        {"timestamp": "2026-01-21T13:00:00Z", "open": 1.1090, "high": 1.1110, "low": 1.1085, "close": 1.1105, "volume": 850},
        {"timestamp": "2026-01-21T13:15:00Z", "open": 1.1105, "high": 1.1125, "low": 1.1100, "close": 1.1120, "volume": 800},
        {"timestamp": "2026-01-21T13:30:00Z", "open": 1.1120, "high": 1.1130, "low": 1.1115, "close": 1.1125, "volume": 780},
        {"timestamp": "2026-01-21T13:45:00Z", "open": 1.1125, "high": 1.1135, "low": 1.1118, "close": 1.1130, "volume": 760},
        {"timestamp": "2026-01-21T14:00:00Z", "open": 1.1130, "high": 1.1140, "low": 1.1125, "close": 1.1135, "volume": 740},
    ]
    
    # 5M candles (most recent)
    candles_5m = [
        {"timestamp": "2026-01-21T13:40:00Z", "open": 1.1095, "high": 1.1100, "low": 1.1092, "close": 1.1098, "volume": 200},
        {"timestamp": "2026-01-21T13:45:00Z", "open": 1.1098, "high": 1.1105, "low": 1.1095, "close": 1.1103, "volume": 210},
        {"timestamp": "2026-01-21T13:50:00Z", "open": 1.1103, "high": 1.1110, "low": 1.1100, "close": 1.1108, "volume": 220},
        {"timestamp": "2026-01-21T13:55:00Z", "open": 1.1108, "high": 1.1115, "low": 1.1105, "close": 1.1112, "volume": 230},
        {"timestamp": "2026-01-21T14:00:00Z", "open": 1.1112, "high": 1.1120, "low": 1.1110, "close": 1.1115, "volume": 240},
    ]
    
    return {
        "symbol": "EURUSD",
        "timestamp": "2026-01-21T14:00:00Z",  # 9:00 AM EST - Within NY Kill Zone (7-10 AM EST)
        "timeframe_bars": {
            "1H": candles_1h,
            "15M": candles_15m,
            "5M": candles_5m
        },
        "account_balance": 10000.0,
        "risk_pct": 1.0,
        "session": "NY",
        "economic_calendar": []  # No high-impact news
    }


def main():
    """Run the ICT Trading System with sample data."""
    # Load rules
    rules_path = PROJECT_ROOT / "rules" / "config.yaml"
    if rules_path.exists():
        load_rules(str(rules_path))
    
    # Initialize Agent
    agent = MainAgent()
    
    # Create sample market snapshot
    snapshot = create_sample_snapshot()
    
    # Initialize Session
    ts_str = snapshot["timestamp"]
    if ts_str.endswith('Z'):
        ts_str = ts_str[:-1] + '+00:00'
        
    start_time = datetime.fromisoformat(ts_str)
    
    agent.initialize_session(
        symbol=snapshot["symbol"],
        mode="BACKTEST",
        start_time=start_time,
        starting_balance=snapshot["account_balance"]
    )
    
    # Run tick
    result = agent.run_tick(
        timeframe_bars=snapshot["timeframe_bars"],
        economic_calendar=snapshot["economic_calendar"]
    )
    
    # Output as JSON
    print(json.dumps(result, indent=2, default=str))
    
    return result


if __name__ == "__main__":
    main()
