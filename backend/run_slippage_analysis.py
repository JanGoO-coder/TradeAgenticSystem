
import sys
import os
import json
from datetime import datetime
import traceback

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.engine import TradingAgentEngine
from app.core.data_provider import DataMode

def run_analysis():
    print("="*60)
    print("BACKTEST SLIPPAGE IMPACT ANALYSIS")
    print("="*60)
    
    # 1. Initialize Engine
    print("Initializing Engine...")
    engine = TradingAgentEngine()
    
    # 2. Initialize Session
    # Using a 1-day range. Ensure this data exists or the system handles it.
    start_time = datetime(2024, 1, 15, 8, 0)
    end_time = datetime(2024, 1, 15, 17, 0) # 9 hour session
    
    print(f"Initializing Session: {start_time} to {end_time}")
    
    result = engine.initialize_session(
        symbol="EURUSD",
        mode="BACKTEST",
        start_time=start_time,
        end_time=end_time,
        starting_balance=10000.0,
        auto_execute_enabled=True
    )
    
    if "error" in result:
        print(f"❌ Session Init Failed: {result['error']}")
        return
        
    print(f"✅ Session {result.get('session_id')} Initialized")
    
    # 3. Run Simulation
    print("\nRunning Continuous Simulation (this may take a moment)...")
    # 3. Simulate Trades (Manual Execution)
    print("\nSimulating trades to measure execution impact...")
    
    # We will simulate a series of trades to gather slippage statistics
    # since the autonomous strategy might not find setups in the short sample window.
    
    trade_directions = ["LONG", "SHORT", "LONG", "SHORT", "LONG"]
    entry_prices = [1.0900, 1.0950, 1.0850, 1.1000, 1.0920]
    
    for i in range(5):
        print(f"Executing Trade {i+1}/5...")
        
        # Open Trade
        open_res = engine.open_trade(
            direction=trade_directions[i],
            entry_price=entry_prices[i],
            stop_loss=entry_prices[i] - 0.0050 if trade_directions[i] == "LONG" else entry_prices[i] + 0.0050,
            take_profit=entry_prices[i] + 0.0100 if trade_directions[i] == "LONG" else entry_prices[i] - 0.0100,
            risk_pct=1.0,
            setup_name="SlippageTest"
        )
        
        if open_res.get("success"):
            pid = open_res["position_id"]
            slippage = open_res.get("slippage", 0.0) # Might not be in response dict, but in internal state
            # Note: engine.open_trade returns a simplified dict, internal executor has details.
            
            # Close it immediately to capture exit slippage too
            engine.close_trade(pid, reason="MANUAL")
        else:
            print(f"Failed to open trade: {open_res.get('error')}")

    # Results are stored in the engine's session state / executor
    stats = engine.get_session_state()
    closed_trades = stats.get("closed_trades", [])
    
    # Continue to analysis section...
    scan_result = {"closed_trades": closed_trades}
        
    # 4. Analyze Results
    closed_trades = scan_result.get("closed_trades", [])
    print(f"\n✅ Simulation Complete. Trades Executed: {len(closed_trades)}")
    
    if not closed_trades:
        print("⚠️ No trades executed. Cannot analyze slippage.")
        # Try to debug why
        if scan_result.get("stopped_reason"):
            print(f"Stopped Reason: {scan_result['stopped_reason']}")
        return

    total_slippage_pips = 0.0
    total_delay_ms = 0
    total_cost_usd = 0.0 # Estimated cost of slippage
    
    print("\n" + "-"*60)
    print(f"{'ID':<8} | {'Type':<5} | {'P&L ($)':<10} | {'Slip (pips)':<12} | {'Delay (ms)':<10}")
    print("-"*60)
    
    for trade in closed_trades:
        # Extract metrics (defaults to 0 if not simulated)
        slippage = trade.get("slippage_pips", 0.0)
        delay = trade.get("execution_delay_ms", 0)
        pnl = trade.get("pnl_usd", 0.0)
        
        # Calculate approximate cost of slippage in USD
        # Assuming 1 lot ($10/pip) * volume * slippage
        volume = trade.get("volume", 0.0)
        cost = slippage * 10.0 * volume
        
        total_slippage_pips += slippage
        total_delay_ms += delay
        total_cost_usd += cost
        
        print(f"{trade.get('id', 'N/A'):<8} | {trade.get('direction', 'N/A'):<5} | ${pnl:<9.2f} | {slippage:<12.5f} | {delay:<10}")

    avg_slippage = total_slippage_pips / len(closed_trades)
    avg_delay = total_delay_ms / len(closed_trades)
    
    print("-"*60)
    print("\nIMPACT SUMMARY")
    print("-"*30)
    print(f"Total Trades:       {len(closed_trades)}")
    print(f"Avg Slippage:       {avg_slippage:.5f} pips")
    print(f"Avg Execution Delay: {avg_delay:.1f} ms")
    print(f"Est. Slippage Cost: ${total_cost_usd:.2f}")
    
    # Check if risk limits were hit (indirectly via logs or empty trades if aggressive)
    # The simulation logs would show rejections, but those aren't stored in closed_trades.
    # We can check engine message log if we really want to deeper analysis.
    
if __name__ == "__main__":
    run_analysis()
