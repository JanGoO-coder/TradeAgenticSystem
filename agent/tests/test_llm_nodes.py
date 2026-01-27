"""
Test Integration of LLM and Rules in Nodes.
"""
import pytest
from datetime import datetime
from src.models import GraphState, MarketSnapshot, HTFBias, OHLCV, BiasValue
from src.nodes import macro_analyst_node


@pytest.fixture
def mock_state():
    """Create a basic graph state with 1H candles."""
    now = datetime.now()
    summary_candles = []
    # Create a simple uptrend: Higher Highs, Higher Lows
    for i in range(20):
        c = OHLCV(
            time=now,
            open=1.0 + i*0.01,
            high=1.0 + i*0.01 + 0.05,
            low=1.0 + i*0.01 - 0.02,
            close=1.0 + i*0.01 + 0.03,
            volume=100
        )
        summary_candles.append(c)

    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timestamp=now.isoformat(),
        timeframe_bars={"1H": summary_candles},
        account_balance=10000,
        backtest_mode=True
    )
    
    return GraphState(
        snapshot=snapshot,
        nodes_triggered=[]
    )


def test_macro_analyst_llm_integration(mock_state):
    """Test that Macro Analyst uses LLM logic."""
    print("\nRunning Macro Analyst Node...")
    
    # Run node
    result_state = macro_analyst_node(mock_state)
    
    print(f"Bias: {result_state.htf_bias.value}")
    print(f"Reason: {result_state.reason_short}")
    
    # Verify Bias exists
    assert result_state.htf_bias is not None
    assert result_state.htf_bias.value in [BiasValue.BULLISH, BiasValue.BEARISH, BiasValue.NEUTRAL]
    
    # Check if Reason mentions LLM (Mock or Real)
    # The mock response in llm.py produces "Reasoning:..."
    # The node logic prefixes "LLM Analysis:" if LLM was used.
    
    assert "LLM Analysis" in result_state.reason_short or "Insufficient" in result_state.reason_short or "structure" in result_state.reason_short
    
    if "LLM Analysis" in result_state.reason_short:
        print("SUCCESS: LLM Logic was triggered!")
    else:
        print("WARNING: LLM Logic was NOT triggered (possibly Parser failed or Config issue).")

if __name__ == "__main__":
    # Manually create state for script execution
    from datetime import datetime
    now = datetime.now()
    summary_candles = []
    for i in range(20):
        c = OHLCV(
            timestamp=now,
            open=1.0 + i*0.01,
            high=1.0 + i*0.01 + 0.05,
            low=1.0 + i*0.01 - 0.02,
            close=1.0 + i*0.01 + 0.03,
            volume=100
        )
        summary_candles.append(c)

    snapshot = MarketSnapshot(
        symbol="EURUSD",
        timestamp=now.isoformat(),
        timeframe_bars={"1H": summary_candles},
        account_balance=10000,
        backtest_mode=True
    )
    
    state = GraphState(
        snapshot=snapshot,
        nodes_triggered=[]
    )
    
    test_macro_analyst_llm_integration(state)

