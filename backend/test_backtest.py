import requests
import json
import sys
import os

# Add backend directory to path if needed (though running from root with full path usually works)
# But since we use requests to localhost, python path issues are less relevant for the connection itself.

BASE_URL = "http://localhost:8000/api/v1/backtest"

def test_risk_settings():
    print("Testing risk settings...")
    try:
        response = requests.get(f"{BASE_URL}/risk-settings")
        if response.status_code == 200:
            print("Risk settings retrieved successfully:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Failed to get risk settings. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error connecting to server: {e}")

def test_open_trade_no_data():
    print("\nTesting open trade (expecting failure if no data loaded)...")
    payload = {
        "direction": "LONG",
        "entry_price": 1.1000,
        "stop_loss": 1.0950,
        "auto_calculate": True
    }
    try:
        response = requests.post(f"{BASE_URL}/trade/open", json=payload)
        print(f"Status Code: {response.status_code}")
        print(response.json())
    except Exception as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    test_risk_settings()
    test_open_trade_no_data()
