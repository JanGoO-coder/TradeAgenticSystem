
import sys
import os
from datetime import datetime

# Add paths
sys.path.insert(0, "D:/TradeAgenticSystem/backend")
sys.path.insert(0, "D:/TradeAgenticSystem/agent")

try:
    from app.agent.engine import TradingAgentEngine
    
    print("✅ Successfully imported TradingAgentEngine")
    
    engine = TradingAgentEngine()
    print("✅ Engine initialized")
    
    # Mock snapshot data
    snapshot = {
        "symbol": "EURUSD",
        "timestamp": datetime.utcnow().isoformat(),
        "timeframe_bars": {
            "1H": [],
            "15M": [],
            "5M": []
        },
        "economic_calendar": []
    }
    
    print("Running analysis...")
    result = engine.analyze(snapshot)
    print("✅ Analysis successful!")
    print(f"Result keys: {result.keys()}")
    
except Exception as e:
    print(f"❌ Analysis failed: {e}")
    import traceback
    traceback.print_exc()
