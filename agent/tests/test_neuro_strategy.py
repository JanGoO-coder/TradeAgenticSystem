
import sys
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Adjust path to find modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Load .env from backend
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend/.env"))
load_dotenv(env_path)

from agent.src.strategy_agent.agent import StrategyAgent
from agent.src.strategy_agent.models import MarketContextRequest

def test_neuro_strategy():
    print("Initializing Strategy Agent...")
    agent = StrategyAgent()
    
    # Mock Data
    now = datetime.utcnow()
    candles_1h = [
        {"timestamp": now, "open": 100, "high": 105, "low": 95, "close": 102},
        {"timestamp": now, "open": 102, "high": 108, "low": 101, "close": 107}, # Bullish FVG Setup maybe?
        {"timestamp": now, "open": 107, "high": 110, "low": 106, "close": 109},
    ]
    
    request = MarketContextRequest(
        timestamp=now,
        symbol="EURUSD",
        timeframe_bars={"1H": candles_1h},
        economic_calendar=[]
    )
    
    print("Running Analysis...")
    try:
        context = agent._analyze_context(request)
        print("\n--- Analysis Result ---")
        print(f"Bias: {context.bias.direction}")
        print(f"Rationale: {context.bias.rationale}")
        print(f"Environment: {context.environment.status}")
        print("-----------------------")
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_neuro_strategy()
