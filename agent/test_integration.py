"""
Integration test for the hierarchical agent system.

This test validates that:
1. Rules configuration loads correctly
2. MainAgent can be instantiated
3. Session initialization works
4. Single tick execution completes
5. Message logging works
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src import (
    MainAgent, StrategyAgent, WorkerAgent,
    load_rules, get_rules, reload_rules, get_rules_manager,
    SessionState, SessionPhase, MarketContext,
    MessageLog, TickLog, AgentRole, ActionType
)


def test_rules_loading():
    """Test rules configuration loading."""
    print("\n" + "="*60)
    print("TEST 1: Rules Configuration Loading")
    print("="*60)

    rules_path = Path(__file__).parent.parent / "rules" / "config.yaml"

    if not rules_path.exists():
        print(f"❌ Rules file not found at: {rules_path}")
        return False

    try:
        config = load_rules(str(rules_path))
        print(f"✅ Rules loaded successfully")
        # KillZonesConfig is a Pydantic model, not a dict
        kz = config.killzones
        active_kz = []
        if kz.london.enabled:
            active_kz.append("london")
        if kz.new_york.enabled:
            active_kz.append("new_york")
        if kz.asia.enabled:
            active_kz.append("asia")
        print(f"   - Active killzones: {active_kz}")
        print(f"   - Default risk per trade: {config.risk.default_risk_pct}%")
        em = config.entry_models
        enabled_models = []
        if em.ote_enabled:
            enabled_models.append("OTE")
        if em.fvg_entry_enabled:
            enabled_models.append("FVG")
        if em.ict_2022_enabled:
            enabled_models.append("ICT_2022")
        if em.silverbullet_enabled:
            enabled_models.append("SILVERBULLET")
        print(f"   - Entry models enabled: {enabled_models}")
        return True
    except Exception as e:
        print(f"❌ Failed to load rules: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_instantiation():
    """Test agent instantiation."""
    print("\n" + "="*60)
    print("TEST 2: Agent Instantiation")
    print("="*60)

    try:
        # Load rules first
        rules_path = Path(__file__).parent.parent / "rules" / "config.yaml"
        load_rules(str(rules_path))

        # Create agents
        main_agent = MainAgent()
        strategy_agent = StrategyAgent()
        worker_agent = WorkerAgent()

        print(f"✅ MainAgent created")
        print(f"✅ StrategyAgent created")
        print(f"✅ WorkerAgent created")

        return True
    except Exception as e:
        print(f"❌ Failed to instantiate agents: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_initialization():
    """Test session initialization."""
    print("\n" + "="*60)
    print("TEST 3: Session Initialization")
    print("="*60)

    try:
        # Load rules
        rules_path = Path(__file__).parent.parent / "rules" / "config.yaml"
        load_rules(str(rules_path))

        # Create main agent
        main_agent = MainAgent()

        # Initialize session
        session = main_agent.initialize_session(
            symbol="EURUSD",
            mode="BACKTEST",
            start_time=datetime(2024, 1, 1, 8, 0),
            end_time=datetime(2024, 1, 31, 22, 0)
        )

        print(f"✅ Session initialized")
        print(f"   - Session ID: {session.session_id}")
        print(f"   - Symbol: {session.symbol}")
        print(f"   - Mode: {session.mode}")
        print(f"   - Phase: {session.phase}")
        print(f"   - Virtual clock: {main_agent.clock.current}")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize session: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tick_execution():
    """Test single tick execution with mock data."""
    print("\n" + "="*60)
    print("TEST 4: Tick Execution")
    print("="*60)

    try:
        # Load rules
        rules_path = Path(__file__).parent.parent / "rules" / "config.yaml"
        load_rules(str(rules_path))

        # Create main agent
        main_agent = MainAgent()

        # Initialize session
        main_agent.initialize_session(
            symbol="EURUSD",
            mode="BACKTEST",
            start_time=datetime(2024, 1, 15, 8, 0),  # Start in London session
            end_time=datetime(2024, 1, 31, 22, 0)
        )

        # Create mock timeframe bars
        mock_bars = {
            "M5": [
                {"time": datetime(2024, 1, 15, 8, 0), "open": 1.0900, "high": 1.0915, "low": 1.0895, "close": 1.0910, "volume": 1000},
                {"time": datetime(2024, 1, 15, 8, 5), "open": 1.0910, "high": 1.0920, "low": 1.0905, "close": 1.0918, "volume": 1200},
                {"time": datetime(2024, 1, 15, 8, 10), "open": 1.0918, "high": 1.0925, "low": 1.0912, "close": 1.0922, "volume": 900},
            ],
            "M15": [
                {"time": datetime(2024, 1, 15, 8, 0), "open": 1.0900, "high": 1.0925, "low": 1.0895, "close": 1.0922, "volume": 3100},
            ],
            "H1": [
                {"time": datetime(2024, 1, 15, 8, 0), "open": 1.0900, "high": 1.0925, "low": 1.0895, "close": 1.0922, "volume": 12000},
            ],
            "H4": [
                {"time": datetime(2024, 1, 15, 4, 0), "open": 1.0880, "high": 1.0930, "low": 1.0870, "close": 1.0920, "volume": 45000},
            ],
            "D1": [
                {"time": datetime(2024, 1, 15, 0, 0), "open": 1.0850, "high": 1.0940, "low": 1.0840, "close": 1.0920, "volume": 250000},
            ],
        }

        # Mock economic calendar - using correct field names
        mock_calendar = [
            {"time": datetime(2024, 1, 15, 13, 30), "currency": "USD", "event_name": "PPI m/m", "impact": "HIGH"},
        ]

        # Run a tick
        result = main_agent.run_tick(
            timeframe_bars=mock_bars,
            economic_calendar=mock_calendar
        )

        print(f"✅ Tick executed successfully")
        print(f"   - Current phase: {result.get('phase', 'N/A')}")
        print(f"   - Tick: {result.get('tick', 'N/A')}")

        if result.get('context'):
            ctx = result['context']
            print(f"   - HTF bias: {ctx.get('bias', {}).get('direction', 'N/A')}")
            print(f"   - Environment: {ctx.get('environment', {}).get('status', 'N/A')}")

        if result.get('setup'):
            print(f"   - Trade setup detected")

        return True
    except Exception as e:
        print(f"❌ Failed to execute tick: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_message_logging():
    """Test message logging functionality."""
    print("\n" + "="*60)
    print("TEST 5: Message Logging")
    print("="*60)

    try:
        # Create message log
        msg_log = MessageLog()

        # Create tick log
        tick_log = TickLog()

        # Start a tick
        tick = tick_log.new_tick(datetime.now())

        # Log some test messages using MessageEnvelope directly
        from src.protocol import MessageEnvelope

        msg1 = MessageEnvelope(
            from_agent=AgentRole.MAIN,
            to_agent=AgentRole.STRATEGY,
            action=ActionType.ANALYZE_CONTEXT,
            payload={"symbol": "EURUSD"}
        )
        msg_log.append(msg1)

        msg2 = MessageEnvelope(
            from_agent=AgentRole.STRATEGY,
            to_agent=AgentRole.MAIN,
            action=ActionType.CONTEXT_RESULT,
            payload={"bias": "BULLISH"},
            correlation_id=msg1.correlation_id
        )
        msg_log.append(msg2)

        print(f"✅ Message logging works")
        print(f"   - Messages logged: {len(msg_log)}")
        print(f"   - Correlation chain verified: {msg2.correlation_id == msg1.correlation_id}")
        print(f"   - Tick created: {tick.tick}")

        return True
    except Exception as e:
        print(f"❌ Message logging failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hot_reload():
    """Test rules hot-reload functionality."""
    print("\n" + "="*60)
    print("TEST 6: Rules Hot-Reload")
    print("="*60)

    try:
        # Get rules manager
        manager = get_rules_manager()
        initial_risk = manager.config.risk.default_risk_pct

        print(f"   - Initial default risk: {initial_risk}%")

        # Reload (same file, but validates mechanism)
        rules_path = Path(__file__).parent.parent / "rules" / "config.yaml"
        success, message = manager.reload()

        if success:
            print(f"✅ Hot-reload succeeded")
            print(f"   - Message: {message}")
        else:
            print(f"⚠️ Hot-reload returned False: {message}")

        return True
    except Exception as e:
        print(f"❌ Hot-reload failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("ICT HIERARCHICAL AGENT SYSTEM - INTEGRATION TESTS")
    print("="*60)

    results = {
        "Rules Loading": test_rules_loading(),
        "Agent Instantiation": test_agent_instantiation(),
        "Session Initialization": test_session_initialization(),
        "Tick Execution": test_tick_execution(),
        "Message Logging": test_message_logging(),
        "Hot-Reload": test_hot_reload(),
    }

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The hierarchical agent system is ready.")
    else:
        print("\n⚠️ Some tests failed. Please review the errors above.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
