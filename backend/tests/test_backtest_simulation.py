import pytest
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.position_executor import (
    BacktestPositionExecutor,
    OpenPositionRequest,
    TradeDirection,
    CloseReason
)

def test_slippage_and_delay_simulation():
    """Test that slippage and delay are calculated and stored."""
    executor = BacktestPositionExecutor(symbol="EURUSD", starting_balance=10000.0)
    
    # Open a trade
    request = OpenPositionRequest(
        symbol="EURUSD",
        direction=TradeDirection.LONG,
        entry_price=1.1000,
        stop_loss=1.0950,
        risk_pct=1.0
    )
    
    result = executor.open_position(request)
    
    assert result.success
    print(f"Slippage: {result.slippage}, Delay: {result.delay_ms}")
    
    # Delay should be within default range (50-300ms)
    assert 50 <= result.delay_ms <= 300
    
    # Check position state
    pos = result.position
    assert pos.entry_slippage == result.slippage
    assert pos.entry_delay_ms == result.delay_ms
    
    # Check that entry price is adjusted by slippage + spread
    # Long: Ask + Slippage. Ask = Mid + Spread/2
    # Adjusted = Entry + Spread/2 + Slippage
    expected_entry = 1.1000 + (pos.spread_at_entry / 2) + result.slippage
    assert abs(pos.entry_price - expected_entry) < 0.00001

def test_risk_limits_enforcement():
    """Test that daily loss limits reject new trades."""
    executor = BacktestPositionExecutor(symbol="EURUSD", starting_balance=10000.0)
    
    # Set default risk limits (should be defaults in class: 5% daily loss)
    max_loss = 10000.0 * 0.05 # 500
    
    # Manually inject daily loss
    executor._daily_loss = 501.0
    executor._current_day = datetime.utcnow().date()
    
    request = OpenPositionRequest(
        symbol="EURUSD",
        direction=TradeDirection.SHORT,
        entry_price=1.1000,
        stop_loss=1.1100,
        risk_pct=1.0
    )
    
    result = executor.open_position(request)
    
    assert not result.success
    assert not result.risk_check_passed
    assert "Daily loss limit reached" in result.error_message
    
def test_close_trade_updates_risk():
    """Test that closing a losing trade updates daily loss."""
    executor = BacktestPositionExecutor(symbol="EURUSD", starting_balance=10000.0)
    executor._daily_loss = 0.0
    
    # Open trade
    request = OpenPositionRequest(
        symbol="EURUSD",
        direction=TradeDirection.LONG,
        entry_price=1.1000,
        stop_loss=1.0900,
        volume=1.0
    )
    open_res = executor.open_position(request)
    pid = open_res.position_id
    
    # Close trade at a loss
    # Entry ~1.10006 (with spread). 
    # Exit at 1.0900 (Stop Loss level)
    close_res = executor.close_position(
        position_id=pid,
        exit_price=1.0900,
        reason=CloseReason.SL_HIT
    )
    
    assert close_res.success
    assert close_res.realized_pnl < 0
    
    # Daily loss should have increased
    assert executor._daily_loss > 0
    assert abs(executor._daily_loss - abs(close_res.realized_pnl)) < 0.01
    
    # Verify execution stats in closed trade
    closed_trades = executor.get_closed_trades()
    last_trade = closed_trades[-1]
    
    assert "execution_delay_ms" in last_trade
    assert "slippage_pips" in last_trade
    assert last_trade["execution_delay_ms"] > 0 # Sum of entry and exit delay

if __name__ == "__main__":
    # verification script usage
    try:
        test_slippage_and_delay_simulation()
        print("✅ test_slippage_and_delay_simulation passed")
        test_risk_limits_enforcement()
        print("✅ test_risk_limits_enforcement passed")
        test_close_trade_updates_risk()
        print("✅ test_close_trade_updates_risk passed")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
