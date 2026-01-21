# Test the /analyze endpoint
import requests
import json

url = "http://localhost:8000/api/v1/analyze"

payload = {
    "symbol": "EURUSD",
    "timestamp": "2026-01-21T14:00:00Z",
    "timeframe_bars": {
        "1H": [
            {"timestamp": "2026-01-20T06:00:00Z", "open": 1.0800, "high": 1.0820, "low": 1.0790, "close": 1.0810, "volume": 1000},
            {"timestamp": "2026-01-20T07:00:00Z", "open": 1.0810, "high": 1.0830, "low": 1.0795, "close": 1.0825, "volume": 1100},
            {"timestamp": "2026-01-20T08:00:00Z", "open": 1.0825, "high": 1.0850, "low": 1.0820, "close": 1.0845, "volume": 1200},
            {"timestamp": "2026-01-20T09:00:00Z", "open": 1.0845, "high": 1.0880, "low": 1.0840, "close": 1.0870, "volume": 1500},
            {"timestamp": "2026-01-20T10:00:00Z", "open": 1.0870, "high": 1.0885, "low": 1.0860, "close": 1.0875, "volume": 1300},
            {"timestamp": "2026-01-20T11:00:00Z", "open": 1.0875, "high": 1.0890, "low": 1.0865, "close": 1.0880, "volume": 1200},
            {"timestamp": "2026-01-20T12:00:00Z", "open": 1.0880, "high": 1.0885, "low": 1.0850, "close": 1.0855, "volume": 1400},
            {"timestamp": "2026-01-20T13:00:00Z", "open": 1.0855, "high": 1.0860, "low": 1.0830, "close": 1.0840, "volume": 1350},
            {"timestamp": "2026-01-20T14:00:00Z", "open": 1.0840, "high": 1.0855, "low": 1.0825, "close": 1.0850, "volume": 1300},
            {"timestamp": "2026-01-20T15:00:00Z", "open": 1.0850, "high": 1.0900, "low": 1.0845, "close": 1.0895, "volume": 1600},
        ],
        "15M": [
            {"timestamp": "2026-01-21T10:00:00Z", "open": 1.1000, "high": 1.1020, "low": 1.0995, "close": 1.1018, "volume": 500},
            {"timestamp": "2026-01-21T10:15:00Z", "open": 1.1018, "high": 1.1030, "low": 1.1015, "close": 1.1028, "volume": 550},
            {"timestamp": "2026-01-21T10:30:00Z", "open": 1.1028, "high": 1.1032, "low": 1.1012, "close": 1.1015, "volume": 600},
            {"timestamp": "2026-01-21T10:45:00Z", "open": 1.1015, "high": 1.1035, "low": 1.1010, "close": 1.1030, "volume": 700},
            {"timestamp": "2026-01-21T11:00:00Z", "open": 1.1030, "high": 1.1045, "low": 1.1025, "close": 1.1042, "volume": 750},
            {"timestamp": "2026-01-21T11:15:00Z", "open": 1.1042, "high": 1.1055, "low": 1.1038, "close": 1.1050, "volume": 680},
            {"timestamp": "2026-01-21T11:30:00Z", "open": 1.1050, "high": 1.1058, "low": 1.1045, "close": 1.1048, "volume": 650},
            {"timestamp": "2026-01-21T11:45:00Z", "open": 1.1048, "high": 1.1052, "low": 1.1030, "close": 1.1035, "volume": 700},
            {"timestamp": "2026-01-21T12:00:00Z", "open": 1.1035, "high": 1.1040, "low": 1.1020, "close": 1.1025, "volume": 750},
            {"timestamp": "2026-01-21T12:15:00Z", "open": 1.1025, "high": 1.1030, "low": 1.1008, "close": 1.1028, "volume": 900},
            {"timestamp": "2026-01-21T12:30:00Z", "open": 1.1028, "high": 1.1075, "low": 1.1025, "close": 1.1070, "volume": 1200},
            {"timestamp": "2026-01-21T12:45:00Z", "open": 1.1070, "high": 1.1095, "low": 1.1065, "close": 1.1090, "volume": 900},
            {"timestamp": "2026-01-21T13:00:00Z", "open": 1.1090, "high": 1.1110, "low": 1.1085, "close": 1.1105, "volume": 850},
        ],
        "5M": []
    },
    "account_balance": 10000.0,
    "risk_pct": 1.0,
    "economic_calendar": []
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))
