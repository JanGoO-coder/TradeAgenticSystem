import pytest
import asyncio
from datetime import datetime
from app.agent.engine import TradingAgentEngine
from app.core.position_executor import TradeDirection

@pytest.mark.asyncio
async def test_agent_analysis_persistence():
    """
    Test that agent analysis data is correctly persisted through the execution pipeline.
    """
    engine = TradingAgentEngine()
    
    # Initialize backtest session
    session_state = engine.initialize_session(
        symbol="EURUSD",
        mode="BACKTEST",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        starting_balance=10000.0
    )
    with open("debug_output.txt", "w") as f:
        f.write(f"DEBUG: init result: {session_state}\n")

        if "error" in session_state:
             f.write(f"Session init failed: {session_state['error']}\n")
             pytest.fail(f"Session init failed: {session_state['error']}")
        
        if engine.last_error:
             f.write(f"Session init failed: {engine.last_error}\n")
             pytest.fail(f"Session init failed: {engine.last_error}")
        
        if not engine.trading_context:
             f.write("Trading context not set after init\n")
             pytest.fail("Trading context not set after init")
        
        # Mock analysis data
        analysis_data = {
            "rationale": "Test Rationale",
            "confidence": 0.95,
            "confluence_score": 8.5,
            "rule_refs": ["1.1", "2.2"],
            "model_type": "TEST_MODEL"
        }
        
        # Manually trigger open_trade with analysis data
        # simulating what the agent would do
        result = engine.open_trade(
            direction="LONG",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
            setup_name="TEST_SETUP",
            agent_analysis=analysis_data
        )
        
        f.write(f"DEBUG: open_trade result: {result}\n")
        
        if "error" in result:
            f.write(f"open_trade failed: {result['error']}\n")
            pytest.fail(f"open_trade failed: {result['error']}")

        if not result.get("success"):
             f.write(f"open_trade success is False: {result}\n")
             assert result["success"] == True
        
        position_id = result["position_id"]
        
        # Verify open position has the data in PositionExecutor (Source of Truth)
        # The session state might not be updated because we are bypassing MainAgent loop
        executor = engine._trading_context.position_executor
        positions = executor.get_positions()
        
        print(f"Executor Positions: {positions}")
        f.write(f"Executor Positions: {positions}\n")
        
        if not positions:
             f.write("No positions found\n")
             assert len(positions) == 1
             
        pos = positions[0]
        # Pos is PositionState object, convert to dict
        pos_dict = pos.to_dict()
        
        f.write(f"Position data: {pos_dict}\n")
        
        # Check if analysis dict is present
        assert "agent_analysis" in pos_dict
        assert pos_dict["agent_analysis"] == analysis_data
        assert pos_dict["agent_analysis"]["rationale"] == "Test Rationale"
        
        # Close the trade
        close_result = engine.close_trade(
            position_id=position_id,
            exit_price=1.1050,
            reason="MANUAL"
        )
        
        assert close_result["success"] == True
        
        # Verify closed trade has the data
        closed_trades = executor.get_closed_trades()
        assert len(closed_trades) == 1
        trade = closed_trades[0]
        
        f.write(f"Closed trade: {trade}\n")
        
        assert "agent_analysis" in trade
        assert trade["agent_analysis"] == analysis_data
        
        print("Verification Successful: Agent analysis persisted in both OpenPosition and ClosedTrade")

if __name__ == "__main__":
    asyncio.run(test_agent_analysis_persistence())
