"""Test backend imports"""
import sys
sys.path.insert(0, "D:/TradeAgenticSystem/backend")
sys.path.insert(0, "D:/TradeAgenticSystem/agent")

print("Step 1: Testing engine import...")
try:
    from app.agent import engine
    print("  - engine module imported")
    print("  - TradingAgentEngine class:", hasattr(engine, 'TradingAgentEngine'))
    print("  - get_agent_engine function:", hasattr(engine, 'get_agent_engine'))
except Exception as e:
    print(f"❌ engine import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nStep 2: Testing rules router import...")
try:
    from app.api.v1.rules import router
    print("✅ Rules router imported")
except Exception as e:
    print(f"❌ Rules router import failed: {e}")
    import traceback
    traceback.print_exc()

print("\nStep 3: Creating engine instance...")
try:
    from app.agent.engine import get_agent_engine
    eng = get_agent_engine()
    print(f"✅ Engine created: {type(eng).__name__}")
    print(f"   - Agent available: {eng._agent_available}")
except Exception as e:
    print(f"❌ Engine instantiation failed: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
