"""Chat API endpoint for non-WebSocket chat."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.agent.engine import get_agent_engine, TradingAgentEngine

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    """Chat message response."""
    message: str
    suggestions: list[str]
    timestamp: str


@router.post("", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> ChatResponse:
    """
    Send a chat message and get a response.
    
    This is a simple REST endpoint for chat.
    For real-time chat, use the WebSocket endpoint.
    """
    response = generate_response(request.message, engine)
    
    return ChatResponse(
        message=response["message"],
        suggestions=response["suggestions"],
        timestamp=datetime.utcnow().isoformat() + "Z"
    )


def generate_response(message: str, engine: TradingAgentEngine) -> dict:
    """Generate a chat response with suggestions."""
    message_lower = message.lower()
    
    # Session queries
    if any(word in message_lower for word in ["session", "time", "zone", "current"]):
        session = engine.get_current_session()
        kz_status = "Active ✓" if session['kill_zone_active'] else "Not active"
        return {
            "message": f"**Current Session Info**\n\n"
                      f"• Time: {session['current_time_est']} EST\n"
                      f"• Session: {session['session']}\n"
                      f"• Kill Zone: {kz_status}\n"
                      f"• Current Rule: 8.1",
            "suggestions": ["Explain rule 8.1", "What's the bias?", "Show me the rules"]
        }
    
    # Bias queries
    elif any(word in message_lower for word in ["bias", "direction", "trend", "bullish", "bearish"]):
        return {
            "message": "To determine the current bias, I need to analyze market data. "
                      "Click **Analyze Now** on the dashboard to run a full analysis, or "
                      "ask about specific rules like:\n\n"
                      "• Rule 1.1 - HTF Bias determination\n"
                      "• Rule 1.2 - LTF Alignment",
            "suggestions": ["Explain rule 1.1", "Explain rule 1.2", "Run analysis"]
        }
    
    # Rule explanations
    elif "rule 1.1" in message_lower or "htf bias" in message_lower:
        return {
            "message": "**Rule 1.1 - HTF Bias**\n\n"
                      "The 1-Hour directional bias must be established through:\n\n"
                      "• **Bullish**: Higher Highs (HH) + Higher Lows (HL)\n"
                      "• **Bearish**: Lower Highs (LH) + Lower Lows (LL)\n\n"
                      "Only trade when structure is clean and non-overlapping (Rule 1.1.1).",
            "suggestions": ["Explain rule 1.2", "What's rule 2.3?", "Show all rules"]
        }
    
    elif "rule 1.2" in message_lower or "ltf align" in message_lower:
        return {
            "message": "**Rule 1.2 - LTF Alignment**\n\n"
                      "The 15-Minute structure must align with the 1H bias:\n\n"
                      "• If 1H is Bullish → 15M should show bullish structure\n"
                      "• If 1H is Bearish → 15M should show bearish structure\n\n"
                      "External range (1H) takes precedence over internal (15M) per Rule 1.2.1.",
            "suggestions": ["Explain rule 1.1", "What's rule 8.1?", "Show entry rules"]
        }
    
    elif "rule 8.1" in message_lower or "kill zone" in message_lower:
        return {
            "message": "**Rule 8.1 - Kill Zones**\n\n"
                      "Trade only during high-probability windows:\n\n"
                      "• **London KZ**: 2:00 AM - 5:00 AM EST\n"
                      "• **NY KZ**: 7:00 AM - 10:00 AM EST\n\n"
                      "These are the optimal times for ICT setups.",
            "suggestions": ["What's the current session?", "Explain rule 8.4", "Show entry rules"]
        }
    
    elif "rule 3.4" in message_lower or "liquidity" in message_lower:
        return {
            "message": "**Rule 3.4 - Liquidity Sweep**\n\n"
                      "Before entry, price must sweep liquidity:\n\n"
                      "• **For Longs**: Sweep sell-side liquidity (below lows)\n"
                      "• **For Shorts**: Sweep buy-side liquidity (above highs)\n\n"
                      "This confirms smart money has accumulated before the move.",
            "suggestions": ["What's rule 5.2?", "Explain FVG", "Show entry models"]
        }
    
    elif "rule 5.2" in message_lower or "fvg" in message_lower or "fair value" in message_lower:
        return {
            "message": "**Rule 5.2 - Fair Value Gap (FVG)**\n\n"
                      "A 3-candle imbalance pattern:\n\n"
                      "1. Candle 1: Sets the range\n"
                      "2. Candle 2: Creates displacement\n"
                      "3. Candle 3: Leaves a gap between C1 high and C3 low\n\n"
                      "Entry at the 50% (Consequent Encroachment) of the FVG.",
            "suggestions": ["What's rule 6.5?", "Explain ICT 2022", "Show entry models"]
        }
    
    elif "rule 6.5" in message_lower or "ict 2022" in message_lower:
        return {
            "message": "**Rule 6.5 - ICT 2022 Entry Model**\n\n"
                      "High-probability entry sequence:\n\n"
                      "1. **Sweep**: Price takes liquidity\n"
                      "2. **Displacement**: Strong move with imbalance\n"
                      "3. **FVG**: Fair Value Gap forms\n"
                      "4. **Entry**: At FVG retracement\n\n"
                      "This is the primary entry model for the system.",
            "suggestions": ["Explain FVG entry", "What's the bias?", "Run analysis"]
        }
    
    elif any(word in message_lower for word in ["help", "what can", "commands"]):
        return {
            "message": "**I can help you with:**\n\n"
                      "📊 **Market Analysis**\n"
                      "• Current session status\n"
                      "• Bias and structure\n\n"
                      "📚 **ICT Rules**\n"
                      "• Explain any rule (1.1, 1.2, 3.4, 5.2, 6.5, 8.1)\n"
                      "• Entry models\n\n"
                      "Try asking a specific question!",
            "suggestions": ["What's the current session?", "Explain rule 1.1", "Show kill zones"]
        }
    
    else:
        return {
            "message": "I'm here to help with ICT trading concepts and analysis. "
                      "Try asking about:\n\n"
                      "• Current session or kill zone status\n"
                      "• Specific rules (e.g., 'explain rule 1.1')\n"
                      "• Entry models like ICT 2022",
            "suggestions": ["What can you do?", "Current session?", "Explain rule 8.1"]
        }
