"""WebSocket endpoints for real-time streaming."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime

from app.agent.engine import get_agent_engine, TradingAgentEngine
from app.core.config import get_settings

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Sends:
    - Session updates every second
    - Analysis results when triggered
    - Chat responses
    """
    engine = get_agent_engine()
    await manager.connect(websocket)
    
    try:
        # Start background task for session updates
        session_task = asyncio.create_task(send_session_updates(websocket, engine))
        
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "analyze":
                # Run analysis
                await handle_analyze(websocket, engine, data.get("payload", {}))
            
            elif message_type == "chat":
                # Handle chat message
                await handle_chat(websocket, engine, data.get("message", ""))
            
            elif message_type == "ping":
                await manager.send_personal_message({"type": "pong"}, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await manager.send_personal_message({
            "type": "error",
            "message": str(e)
        }, websocket)
        manager.disconnect(websocket)


async def send_session_updates(websocket: WebSocket, engine: TradingAgentEngine):
    """Send session updates every second."""
    while True:
        try:
            session_info = engine.get_current_session()
            await manager.send_personal_message({
                "type": "session_update",
                "data": session_info
            }, websocket)
            await asyncio.sleep(1)
        except:
            break


async def handle_analyze(websocket: WebSocket, engine: TradingAgentEngine, payload: dict):
    """Handle analysis request via WebSocket."""
    # Send status update
    await manager.send_personal_message({
        "type": "analysis_started",
        "timestamp": datetime.utcnow().isoformat()
    }, websocket)
    
    try:
        # Run analysis
        result = engine.analyze(payload)
        
        await manager.send_personal_message({
            "type": "analysis_complete",
            "data": result
        }, websocket)
    except Exception as e:
        await manager.send_personal_message({
            "type": "analysis_error",
            "message": str(e)
        }, websocket)


async def handle_chat(websocket: WebSocket, engine: TradingAgentEngine, message: str):
    """Handle chat message and generate response."""
    # Parse the message and generate appropriate response
    response = generate_chat_response(message, engine)
    
    await manager.send_personal_message({
        "type": "chat_response",
        "message": response
    }, websocket)


def generate_chat_response(message: str, engine: TradingAgentEngine) -> str:
    """Generate a response to a chat message."""
    message_lower = message.lower()
    
    # Current session/bias queries
    if any(word in message_lower for word in ["bias", "direction", "trend"]):
        session = engine.get_current_session()
        return f"The current session is {session['session']}. Kill zone is {'active' if session['kill_zone_active'] else 'not active'}. To get the current bias, run an analysis with market data."
    
    elif any(word in message_lower for word in ["session", "time", "zone"]):
        session = engine.get_current_session()
        kz_status = "Active" if session['kill_zone_active'] else "Not active"
        return f"Current time is {session['current_time_est']} EST. Session: {session['session']}. Kill Zone: {kz_status}."
    
    elif any(word in message_lower for word in ["rule 1.1", "htf bias"]):
        return "Rule 1.1 (HTF Bias): The 1H directional bias must be established through Higher Highs/Higher Lows (bullish) or Lower Highs/Lower Lows (bearish). Trades are only allowed when 1H structure is clean and non-overlapping."
    
    elif any(word in message_lower for word in ["rule 8.1", "kill zone"]):
        return "Rule 8.1 (Kill Zones): Trade only during London KZ (2:00-5:00 AM EST) or NY KZ (7:00-10:00 AM EST). These are the highest probability trading windows."
    
    elif any(word in message_lower for word in ["rule", "explain"]):
        return "Which rule would you like me to explain? Available rules: 1.1 (HTF Bias), 1.2 (LTF Alignment), 3.4 (Liquidity Sweep), 5.2 (FVG), 6.5 (ICT 2022), 7.2 (R:R Minimum), 8.1 (Kill Zones)."
    
    elif any(word in message_lower for word in ["analyze", "trade", "setup"]):
        return "To analyze the market, click 'Analyze Now' on the dashboard or send sample market data with your request."
    
    elif any(word in message_lower for word in ["help", "what can"]):
        return "I can help with: 1) Explaining ICT rules 2) Current session status 3) Trade analysis questions. Try asking 'What is rule 8.1?' or 'What's the current session?'"
    
    else:
        return "I understand you're asking about trading. Could you be more specific? Try asking about rules, sessions, or trade setups."


# ============================================================================
# Live Data Streaming
# ============================================================================

from app.services.mt5_service import get_mt5_service
from app.api.v1.data import get_current_config


class LiveConnectionManager:
    """Manages live data WebSocket connections per symbol."""
    
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.connections:
            self.connections[symbol] = []
        self.connections[symbol].append(websocket)
    
    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.connections and websocket in self.connections[symbol]:
            self.connections[symbol].remove(websocket)
    
    async def send_to_symbol(self, symbol: str, message: dict):
        if symbol in self.connections:
            for ws in self.connections[symbol]:
                try:
                    await ws.send_json(message)
                except:
                    pass


live_manager = LiveConnectionManager()


@router.websocket("/ws/live/{symbol}")
async def live_data_stream(websocket: WebSocket, symbol: str):
    """
    Stream live analysis updates for a specific symbol.
    
    Uses the configured refresh interval from data settings.
    Fetches fresh MT5 data and runs analysis on each interval.
    """
    engine = get_agent_engine()
    mt5_service = get_mt5_service()
    
    await live_manager.connect(websocket, symbol)
    
    try:
        # Get initial config
        config = get_current_config()
        refresh_interval = config.live_refresh_interval
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "symbol": symbol,
            "refresh_interval": refresh_interval,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            try:
                # Check for messages (non-blocking)
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=0.1
                    )
                    
                    # Handle control messages
                    if data.get("type") == "set_interval":
                        refresh_interval = data.get("interval", 60)
                        await websocket.send_json({
                            "type": "interval_updated",
                            "interval": refresh_interval
                        })
                    
                    elif data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    
                except asyncio.TimeoutError:
                    pass
                
                # Fetch fresh data
                if mt5_service.is_connected:
                    # Use real MT5 data
                    snapshot = {
                        "symbol": symbol,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "timeframe_bars": {
                            "1H": mt5_service.get_latest_bars(symbol, "1H", config.htf_bars),
                            "15M": mt5_service.get_latest_bars(symbol, "15M", config.ltf_bars),
                            "5M": mt5_service.get_latest_bars(symbol, "5M", config.micro_bars),
                        },
                        "account_balance": 10000.0,
                        "risk_pct": 1.0,
                        "economic_calendar": []
                    }
                else:
                    # Use generated sample data
                    snapshot = generate_sample_snapshot(symbol, config)
                
                # Run analysis
                result = engine.analyze(snapshot)
                
                # Send to client
                await websocket.send_json({
                    "type": "analysis",
                    "data": result,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "mt5" if mt5_service.is_connected else "sample"
                })
                
                # Wait for configured interval
                await asyncio.sleep(refresh_interval)
                
                # Refresh config in case it changed
                config = get_current_config()
                refresh_interval = config.live_refresh_interval
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                await asyncio.sleep(5)  # Wait before retrying
    
    except WebSocketDisconnect:
        pass
    finally:
        live_manager.disconnect(websocket, symbol)


def generate_sample_snapshot(symbol: str, config) -> dict:
    """Generate sample market data snapshot for live mode fallback."""
    import math
    
    seed = sum(ord(c) for c in symbol)
    base_price = 1.08 if "EUR" in symbol else 150.0 if "JPY" in symbol else 2000.0 if "XAU" in symbol else 1.0
    volatility = 0.002
    
    def generate_bars(count: int, tf: str):
        bars = []
        price = base_price
        for i in range(count):
            timestamp = datetime.utcnow().timestamp() - (count - i) * (3600 if tf == "1H" else 900 if tf == "15M" else 300)
            change = (math.sin(seed + i * 0.1 + datetime.utcnow().timestamp() * 0.001) * volatility)
            high = price * (1 + abs(change) + volatility * 0.5)
            low = price * (1 - abs(change) - volatility * 0.5)
            close = price * (1 + change)
            
            bars.append({
                "timestamp": datetime.utcfromtimestamp(timestamp).isoformat() + "Z",
                "open": round(price, 5),
                "high": round(high, 5),
                "low": round(low, 5),
                "close": round(close, 5),
                "volume": 1000 + seed % 500 + i * 10
            })
            price = close
        return bars
    
    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "timeframe_bars": {
            "1H": generate_bars(config.htf_bars, "1H"),
            "15M": generate_bars(config.ltf_bars, "15M"),
            "5M": generate_bars(config.micro_bars, "5M"),
        },
        "account_balance": 10000.0,
        "risk_pct": 1.0,
        "economic_calendar": []
    }

