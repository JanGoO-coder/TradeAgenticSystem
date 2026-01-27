"""
AI Chat API Endpoint.

RAG-powered conversational interface for strategy questions.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.services.llm_service import get_gemini_service
from app.services.strategy_store import get_strategy_store

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str = Field(..., description="User message")
    context: Optional[dict] = Field(None, description="Optional context (current analysis, etc)")
    history: Optional[List[dict]] = Field(None, description="Conversation history")


class ChatResponse(BaseModel):
    """Chat message response."""
    message: str
    sources: List[dict]
    suggestions: List[str]
    timestamp: str


SYSTEM_PROMPT = """You are an ICT (Inner Circle Trader) trading assistant.

Your role is to:
1. Answer questions about ICT trading concepts and rules
2. Explain strategy rules when asked
3. Help users understand market analysis
4. Provide educational context about trading concepts

You have access to the ICT Rulebook and can cite specific rules.
When referencing rules, use the format "Rule X.X" (e.g., "Rule 6.5").

Be concise but thorough. Use markdown formatting for clarity.
If you don't know something, say so - don't make up trading advice.

IMPORTANT: Never provide specific trading signals or financial advice.
Always remind users that trading involves risk."""


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a chat message and get an AI-powered response.

    Uses RAG to retrieve relevant strategy sections and
    Gemini to generate contextual responses.
    """
    try:
        gemini = get_gemini_service()
        strategy_store = await get_strategy_store()

        # Search for relevant strategies
        relevant_strategies = await strategy_store.search_strategies(
            request.message,
            k=3
        )

        # Build context from strategies
        strategy_context = ""
        if relevant_strategies:
            strategy_context = "\n\n---\n\n**Relevant Rules:**\n\n"
            for r in relevant_strategies:
                strategy_context += f"### {r['headers']}\n{r['content'][:500]}...\n\n"

        # Build prompt
        prompt_parts = [
            f"User question: {request.message}",
        ]

        if strategy_context:
            prompt_parts.append(strategy_context)

        if request.context:
            prompt_parts.append(f"\nCurrent context: {request.context}")

        if request.history:
            history_str = "\n".join([
                f"{'User' if h.get('role') == 'user' else 'Assistant'}: {h.get('content', '')}"
                for h in request.history[-5:]  # Last 5 messages
            ])
            prompt_parts.append(f"\nConversation history:\n{history_str}")

        prompt = "\n\n".join(prompt_parts)

        # Generate response
        response = await gemini.generate(
            prompt=prompt,
            mode="verbose",
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7
        )

        # Generate suggestions based on context
        suggestions = generate_suggestions(request.message, relevant_strategies)

        # Build sources from relevant strategies
        sources = [
            {
                "rule_ids": r.get("rule_ids", []),
                "source": r.get("source", ""),
                "headers": r.get("headers", ""),
                "score": r.get("score", 0)
            }
            for r in relevant_strategies
        ]

        return ChatResponse(
            message=response.get("content", "I'm sorry, I couldn't generate a response."),
            sources=sources,
            suggestions=suggestions,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    except Exception as e:
        # Fallback to rule-based responses if LLM fails
        return fallback_response(request.message)


def generate_suggestions(message: str, strategies: List[dict]) -> List[str]:
    """Generate follow-up suggestions based on context."""
    suggestions = []

    message_lower = message.lower()

    # Based on topic
    if "bias" in message_lower:
        suggestions.extend([
            "How do I identify structure?",
            "What is LTF alignment?",
            "Explain Rule 1.1"
        ])
    elif "fvg" in message_lower or "fair value" in message_lower:
        suggestions.extend([
            "What's an Order Block?",
            "How to trade FVGs?",
            "Explain premium/discount"
        ])
    elif "liquidity" in message_lower or "sweep" in message_lower:
        suggestions.extend([
            "What are equal highs/lows?",
            "Explain stop hunts",
            "What is Rule 3.4?"
        ])
    elif "session" in message_lower or "kill zone" in message_lower:
        suggestions.extend([
            "Best times to trade?",
            "Explain London KZ",
            "What is Power of Three?"
        ])
    elif "entry" in message_lower or "setup" in message_lower:
        suggestions.extend([
            "What is OTE?",
            "Explain the 2022 Model",
            "Entry confirmation rules"
        ])

    # Add rule suggestions from strategies
    for s in strategies[:2]:
        rule_ids = s.get("rule_ids", [])
        for rule_id in rule_ids[:1]:
            suggestions.append(f"Explain Rule {rule_id}")

    # Ensure unique suggestions
    return list(dict.fromkeys(suggestions))[:4]


def fallback_response(message: str) -> ChatResponse:
    """Fallback responses when LLM is unavailable."""
    message_lower = message.lower()

    if "rule 1.1" in message_lower or "htf bias" in message_lower:
        response = """**Rule 1.1 - HTF Bias**

The 1-Hour directional bias must be established through:

• **Bullish**: Higher Highs (HH) + Higher Lows (HL)
• **Bearish**: Lower Highs (LH) + Lower Lows (LL)

Only trade when structure is clean and non-overlapping."""
        suggestions = ["Explain Rule 1.2", "What's LTF alignment?"]

    elif "rule 8.1" in message_lower or "kill zone" in message_lower:
        response = """**Rule 8.1 - Kill Zones**

Trade only during high-probability windows:

• **London KZ**: 2:00 AM - 5:00 AM EST
• **NY KZ**: 7:00 AM - 10:00 AM EST

These are the optimal times for ICT setups."""
        suggestions = ["Explain Power of Three", "Best session to trade?"]

    elif "fvg" in message_lower or "fair value gap" in message_lower:
        response = """**Rule 5.2 - Fair Value Gap (FVG)**

An FVG is a 3-candle imbalance:

• **Bullish FVG**: Gap between candle 1 high and candle 3 low
• **Bearish FVG**: Gap between candle 1 low and candle 3 high

Price often returns to fill these gaps."""
        suggestions = ["What's an Order Block?", "Explain OTE"]

    else:
        response = """I can help you understand ICT trading concepts!

Try asking about:
• Market structure and bias (Rule 1.1)
• Kill zones and sessions (Rule 8.1)
• Fair Value Gaps (Rule 5.2)
• Liquidity and sweeps (Rule 3.4)
• Entry models (Rule 6.5)"""
        suggestions = ["Explain Rule 1.1", "What is a kill zone?", "How to find FVGs?"]

    return ChatResponse(
        message=response,
        sources=[],
        suggestions=suggestions,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
