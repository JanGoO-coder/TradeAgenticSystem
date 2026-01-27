"""
System Verification Script (Standalone)

Verifies the integration of MainAgent, StrategyAgent, and WorkerAgent
using the new Reliable Protocol.

Goals:
1. Simulate a full trading loop (Analyze -> Valid Context -> Setup -> Execute -> Receipt).
2. Verify 'reliablity' features (Idempotency, Receipts).
3. Ensure no side effects or crashes.
"""
import sys
import os
import logging
import uuid
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("VERIFY")

# Import Agents and Models
from agent.src.main_agent.agent import MainAgent
from agent.src.strategy_agent.agent import StrategyAgent
from agent.src.worker_agent.agent import WorkerAgent
from agent.src.protocol import ActionType, MessageEnvelope, AgentRole
from agent.src.rules_config import RulesConfig, get_rules
from agent.src.state import (
    SessionPhase, EnvironmentStatus, TradeSetup, 
    BiasDirection, OrderDirection, OrderType,
    TradingSession, EnvironmentCheck, BiasAssessment, SessionLevels, MarketContext
)

# Mock Data Generator
def generate_bullish_context(timestamp: datetime):
    """Creates a mock MarketContext that triggers 'GO' status."""
    return MarketContext(
        bias=BiasAssessment(
             direction=BiasDirection.BULLISH,
             confidence=0.9,
             rationale="Mock Bullish Bias"
        ),
        environment=EnvironmentCheck(
            status=EnvironmentStatus.GO,
            session=TradingSession.NEW_YORK,
            killzone_active=True,
            killzone_name="NY_AM",
            news_clear=True,
            silverbullet_active=False
        ),
        levels=SessionLevels(pdh=1.0500, pdl=1.0400),
        analyzed_at=timestamp,
        valid_until=timestamp + timedelta(minutes=15)
    )

def generate_ohlcv(start_time: datetime, count: int = 5):
    """Generates simple OHLCV bars."""
    bars = []
    price = 1.0450
    for i in range(count):
        t = start_time + timedelta(minutes=5*i)
        # Create a "sweep" candle (Low sweeps then closes high) to trigger ICT/Turtle logic
        bars.append({
            "timestamp": t.isoformat(),
            "open": price,
            "high": price + 0.0010,
            "low": price - 0.0010,
            "close": price + 0.0005,
            "volume": 1000
        })
        price += 0.0005
    return bars

# Mock Execution Handler
def mock_execution_handler(**kwargs):
    logger.info(f"BROKER: Executing {kwargs['direction']} @ {kwargs['entry_price']}")
    return {
        "success": True,
        "position_id": f"pos_{uuid.uuid4().hex[:8]}",
        "entry_price": kwargs['entry_price'],
        "volume": 1.0,
        "take_profit": kwargs['take_profit'],
        "message": "Filled by MockBroker"
    }

def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")

def main():
    print_separator("INITIALIZATION")
    
    # 1. Setup Agents
    config = get_rules()
    # Force some config to ensure we find trades
    config.timeframes.bias_timeframe = "1H"
    config.timeframes.entry_timeframes = ["5M"]
    
    main_agent = MainAgent(
        config=config,
        execution_handler=mock_execution_handler
    )
    
    # Initialize Session
    start_time = datetime.utcnow()
    main_agent.initialize_session(
        symbol="EURUSD",
        mode="BACKTEST",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        starting_balance=10000.0,
        timeframe="5M"
    )
    
    print("Agents initialized.")
    print(f"Main Agent Phase: {main_agent.state.phase}")

    # =========================================================================
    # TICK 1: ANALYZING
    # =========================================================================
    print_separator("TICK 1: ANALYSIS REQUEST")
    
    # In 'ANALYZING' phase, Main requests context.
    # NOTE: Since our Strat Agent is "pure", it will reply immediately in synchronous mode.
    # We cheat slightly by mocking the Strategy response to ensure we get a "GO" signal 
    # without needing perfect historical data for the complex analysis tools.
    
    # Monkey-patch strategy analysis for deterministic testing
    original_analyze = main_agent.strategy_agent._analyze_context
    main_agent.strategy_agent._analyze_context = lambda req: generate_bullish_context(req.timestamp)
    logger.info("Monkey-patched StrategyAgent to force BULLISH GO context.")

    current_time = start_time
    ohlcv = generate_ohlcv(current_time)
    
    # Run Tick
    result = main_agent.run_tick({
        "1H": ohlcv, # reuse 5m as 1h for simplicity, just needs data presence
        "5M": ohlcv
    }, [])
    
    print(f"Tick Result: {json.dumps(result, indent=2, default=str)}")
    print(f"State: {main_agent.state.phase}")
    
    # Expectation: 
    # 1. Main sends ANALYZE_CONTEXT
    # 2. Strat replies CONTEXT_RESULT (GO)
    # 3. Main updates state -> DECIDING -> EXECUTING (if using optimized transitions) or stays DECIDING
    
    if main_agent.state.phase == SessionPhase.DECIDING or main_agent.state.phase == SessionPhase.EXECUTING:
        print("SUCCESS: Moved past ANALYZING.")
    else:
        print("WARNING: Stuck in ANALYZING?")

    # =========================================================================
    # TICK 2: EXECUTION REQUEST
    # =========================================================================
    print_separator("TICK 2: SCAN & EXECUTE")
    
    # If in DECIDING, next tick checks context and moves to EXECUTING.
    # If in EXECUTING, next tick scans for setups.
    
    # We need the Worker to actually find a trade.
    # Monkey-patch Worker scan to force a setup
    def mock_scan(*args, **kwargs):
        return [TradeSetup(
            model_name="TEST_MODEL",
            model_type="ENTRY",
            entry_price=1.0500,
            entry_type=OrderType.LIMIT,
            direction=OrderDirection.LONG,
            stop_loss=1.0480,
            take_profit=1.0540,
            risk_reward=2.0,
            confidence=0.9,
            confluence_score=10,
            confluence_factors=["Mock"],
            rationale="Forced verify setup"
        )]
    
    main_agent.worker_agent._scan_all_models = mock_scan
    logger.info("Monkey-patched WorkerAgent to force valid TradeSetup.")
    
    # Advance time slightly
    current_time += timedelta(minutes=5)
    
    result = main_agent.run_tick({
        "1H": ohlcv, 
        "5M": ohlcv
    }, [])
    
    print(f"Tick Result: {json.dumps(result, indent=2, default=str)}")
    print(f"State: {main_agent.state.phase}")
    
    # Check if we have a pending request (ReliabilityState)
    rel_state = main_agent._rel_state
    if rel_state.pending_request:
        print(f"Pending Reliable Request: {rel_state.pending_request.action}")
        print(f"Correlation ID: {rel_state.pending_request.correlation_id}")
    else:
        print("No pending request (maybe executed synchronously?).")

    # =========================================================================
    # IDEMPOTENCY CAGE MATCH
    # =========================================================================
    print_separator("TEST: IDEMPOTENCY & SAFETY")
    
    worker = main_agent.worker_agent
    
    # Construct a raw Execution Request
    corr_id = f"test_corr_{uuid.uuid4().hex[:8]}"
    msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    
    exec_payload = {
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry_price": 1.0500,
        "stop_loss": 1.0450, 
        "take_profit": 1.0600,
        "setup_name": "TEST_IDEMPOTENCY",
        "risk_pct": 0.01
    }
    
    envelope = MessageEnvelope(
        id=msg_id,
        correlation_id=corr_id,
        from_agent=AgentRole.MAIN,
        to_agent=AgentRole.WORKER,
        action=ActionType.EXECUTE_ORDER,
        payload=exec_payload
    )
    
    print(f"Attempt 1: Sending Valid Order {corr_id}")
    reply1 = worker.handle_message(envelope)
    print(f"Reply 1: {reply1.action} | Status: {reply1.payload.get('status')}")
    
    if reply1.action != ActionType.EXECUTION_RECEIPT:
        print("FAILED: Attempt 1 did not get receipt.")
        return

    print(f"Attempt 2: Resending SAME Envelope {corr_id}")
    reply2 = worker.handle_message(envelope)
    print(f"Reply 2: {reply2.action} | Status: {reply2.payload.get('status')}")
    
    # Assertions
    if reply1.id != reply2.id:
        # Note: In strict idempotency, we might return the EXACT same envelope object, 
        # or a new envelope with identical payload. The Worker implementation returns from cache `_execution_receipts`.
        # So IDs might differ if `create_reply` generates a new ID, UNLESS we cached the *entire envelope*.
        # Looking at WorkerAgent code: `self._execution_receipts[message.correlation_id] = response`.
        # So it returns the exact same object.
        if reply1.payload == reply2.payload:
             print("SUCCESS: Payloads match (Loose Idempotency)")
        else:
             print("FAILURE: Payloads differ!")
    else:
        print("SUCCESS: Exact same envelope returned (Strict Idempotency)")

    # Test Safety Catch
    print("\nAttempt 3: sending UNSAFE order (SL > Entry for Long)")
    unsafe_payload = exec_payload.copy()
    unsafe_payload["stop_loss"] = 1.0550 # Invalid for Long entry 1.0500
    
    unsafe_env = MessageEnvelope(
        id=f"msg_{uuid.uuid4().hex}",
        correlation_id=f"unsafe_{uuid.uuid4().hex}",
        from_agent=AgentRole.MAIN,
        to_agent=AgentRole.WORKER,
        action=ActionType.EXECUTE_ORDER,
        payload=unsafe_payload
    )
    
    reply3 = worker.handle_message(unsafe_env)
    print(f"Reply 3: {reply3.action} | Error: {reply3.error}")
    
    if reply3.action == ActionType.NACK or reply3.action == ActionType.ERROR:
        print("SUCCESS: Unsafe order rejected.")
    else:
        print(f"FAILURE: Unsafe order accepted? {reply3.action}")

    print_separator("FINAL AUDIT")
    # Print a few logs from Main Agent to prove traceability
    print("Main Agent Message Log (Last 5):")
    for msg in main_agent.message_log.get_last(5):
        print(f"[{msg.timestamp.strftime('%H:%M:%S')}] {msg.from_agent} -> {msg.to_agent} : {msg.action}")

if __name__ == "__main__":
    main()
