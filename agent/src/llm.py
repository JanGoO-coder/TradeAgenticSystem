"""
LLM Service for Agentic Decision Making.

This module provides a unified interface for the agent to query an LLM
for reasoning about rules and market context.
"""
import os
import logging
from typing import Dict, Any, Optional

# We use LangChain for abstraction
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


logger = logging.getLogger(__name__)

class LLMService:
    """Service to interact with LLMs for rule reasoning."""

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        self.model_name = model_name
        # Assumes GOOGLE_API_KEY is in env
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not found. LLM features will return mock responses.")
            self.llm = None
        else:
            try:
                self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.1, google_api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None


    def ask_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Query the LLM with a specific system and user prompt.
        
        Returns:
            String response content.
        """
        if not self.llm:
            return self._mock_response(system_prompt, user_prompt)

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM Query Failed: {e}")
            return f"ERROR: LLM query failed - {str(e)}"

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """Provide fallback responses if no LLM is available (for testing)."""
        logger.info("Generating MOCK LLM response.")
        
        if "Rule 1.1" in system_prompt:
             return """
Reasoning:
1. Reviewing Rule 1.1: 1H Bias is determined by swing highs/lows.
2. Market Data shows Higher Highs (HH) and Higher Lows (HL).
3. Displacement is present.
Conclusion: BULLISH
             """.strip()
        
        return "MOCK RESPONSE: LLM not configured."

# Singleton
_llm_service = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
