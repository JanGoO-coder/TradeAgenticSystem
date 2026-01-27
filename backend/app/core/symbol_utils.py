"""Shared symbol utilities for consistent pip/point calculations across the codebase.

This module centralizes instrument-specific calculations to avoid code duplication
and ensure consistency across backend services and agent code.
"""
from typing import Tuple


def get_pip_multiplier(symbol: str) -> int:
    """
    Get the pip multiplier for a given symbol.
    
    This determines how many price units equal one pip:
    - Standard Forex (EURUSD, GBPUSD, etc.): 1 pip = 0.0001 → multiplier = 10000
    - JPY pairs (USDJPY, EURJPY, etc.): 1 pip = 0.01 → multiplier = 100
    - Gold (XAUUSD): 1 pip = 0.10 → multiplier = 10
    - Indices (US30, NAS100, etc.): 1 pip = 1.0 → multiplier = 1
    
    Args:
        symbol: Trading symbol (e.g., "EURUSD", "XAUUSD", "US30")
        
    Returns:
        Integer multiplier to convert price difference to pips
    """
    symbol_upper = symbol.upper() if symbol else ""
    
    # Gold and precious metals
    if "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return 10
    
    # Silver
    if "XAG" in symbol_upper or "SILVER" in symbol_upper:
        return 100
    
    # JPY pairs
    if "JPY" in symbol_upper:
        return 100
    
    # Major indices
    if any(idx in symbol_upper for idx in ["US30", "US500", "NAS", "SPX", "DAX", "FTSE", "DJ30"]):
        return 1
    
    # Crypto (typically large decimals)
    if any(crypto in symbol_upper for crypto in ["BTC", "ETH", "LTC", "XRP"]):
        return 1
    
    # Default: standard forex pairs
    return 10000


def get_pip_value_per_lot(symbol: str) -> float:
    """
    Get the pip value in USD per standard lot for a given symbol.
    
    This is an approximation. Actual pip value depends on:
    - Account currency
    - Current exchange rate for cross-currency pairs
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Approximate pip value in USD per standard lot
    """
    symbol_upper = symbol.upper() if symbol else ""
    
    # Gold: ~$1 per pip per lot
    if "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return 1.0
    
    # Major indices: varies widely
    if any(idx in symbol_upper for idx in ["US30", "NAS", "SPX", "DAX"]):
        return 1.0
    
    # JPY pairs: ~$10 per pip per lot (approximate)
    if "JPY" in symbol_upper:
        return 10.0
    
    # Standard forex: $10 per pip per standard lot
    return 10.0


def get_price_decimals(symbol: str) -> int:
    """
    Get the number of decimal places for price display.
    
    Args:
        symbol: Trading symbol
        
    Returns:
        Number of decimal places
    """
    symbol_upper = symbol.upper() if symbol else ""
    
    if "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return 2
    
    if "JPY" in symbol_upper:
        return 3
    
    if any(idx in symbol_upper for idx in ["US30", "NAS", "SPX", "DAX"]):
        return 1
    
    return 5  # Standard forex


def calculate_pips(
    entry_price: float,
    exit_price: float,
    symbol: str,
    is_long: bool = True
) -> float:
    """
    Calculate pip difference between two prices.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        symbol: Trading symbol (for pip multiplier)
        is_long: True for long position, False for short
        
    Returns:
        Pip difference (positive for profit, negative for loss)
    """
    multiplier = get_pip_multiplier(symbol)
    
    if is_long:
        return (exit_price - entry_price) * multiplier
    else:
        return (entry_price - exit_price) * multiplier


def calculate_pnl_usd(
    pips: float,
    volume: float,
    symbol: str
) -> float:
    """
    Calculate P&L in USD from pips.
    
    Args:
        pips: Pip profit/loss
        volume: Position volume in lots
        symbol: Trading symbol
        
    Returns:
        P&L in USD
    """
    pip_value = get_pip_value_per_lot(symbol)
    return pips * pip_value * volume


def get_symbol_type(symbol: str) -> str:
    """
    Determine the instrument type for a symbol.
    
    Args:
        symbol: Trading symbol
        
    Returns:
        One of: "forex", "gold", "silver", "index", "crypto", "unknown"
    """
    symbol_upper = symbol.upper() if symbol else ""
    
    if "XAU" in symbol_upper or "GOLD" in symbol_upper:
        return "gold"
    
    if "XAG" in symbol_upper or "SILVER" in symbol_upper:
        return "silver"
    
    if any(idx in symbol_upper for idx in ["US30", "US500", "NAS", "SPX", "DAX", "FTSE"]):
        return "index"
    
    if any(crypto in symbol_upper for crypto in ["BTC", "ETH", "LTC", "XRP"]):
        return "crypto"
    
    # Check for common forex patterns
    forex_currencies = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]
    if any(curr in symbol_upper for curr in forex_currencies):
        return "forex"
    
    return "unknown"
