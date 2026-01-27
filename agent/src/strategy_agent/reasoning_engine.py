"""
Reasoning Engine (The Brain).

The LLM-backed decision-making core of the Neuro-Symbolic Architecture.
Connects to Gemini via Backend Service to interpret market facts against strategies.
"""
import sys
import os
import logging
from typing import Dict, Any, Literal, Optional, List
from pydantic import BaseModel, Field, ValidationError

# Add backend path to sys.path to allow importing services
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir))) 
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from backend.app.services.llm_client import GeminiClient
    from backend.app.services.prompts import build_analysis_prompt
except ImportError:
    logging.error("Could not import backend services. Ensure PYTHONPATH includes project root.")
    GeminiClient = None
    build_analysis_prompt = None

logger = logging.getLogger(__name__)


# =============================================================================
# Extended Decision Schema
# =============================================================================

class KeyLevels(BaseModel):
    """Suggested trading levels from LLM analysis."""
    entry_zone: Optional[List[float]] = Field(
        default=None,
        description="[low_price, high_price] for entry zone"
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Suggested stop loss price"
    )
    target: Optional[float] = Field(
        default=None,
        description="Suggested take profit price"
    )


class DecisionSchema(BaseModel):
    """
    Validated output from LLM reasoning.
    
    Extended from basic schema to include:
    - key_levels: Suggested entry/SL/TP if action is TRADE
    - structure_assessment: Brief summary of market structure interpretation
    - session_assessment: Brief summary of time/session validity
    - entry_conditions_met: List of conditions that are satisfied
    - blocking_factors: List of reasons preventing trade (if WAIT)
    """
    # Core decision fields (required)
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    action: Literal["TRADE", "MONITOR", "WAIT"]
    
    # Extended fields for transparency (optional)
    key_levels: Optional[KeyLevels] = None
    structure_assessment: Optional[str] = None
    session_assessment: Optional[str] = None
    entry_conditions_met: Optional[List[str]] = Field(default_factory=list)
    blocking_factors: Optional[List[str]] = Field(default_factory=list)
    
    class Config:
        extra = "ignore"  # Ignore any extra fields LLM might produce


# =============================================================================
# Reasoning Engine
# =============================================================================

class ReasoningEngine:
    """
    LLM-backed Reasoning Engine.
    
    The "brain" of the Neuro-Symbolic architecture that:
    1. Receives pure market facts (from observers)
    2. Receives natural language strategy (from playbook)
    3. Constructs a structured prompt
    4. Queries the LLM for a decision
    5. Validates and returns the decision
    """
    
    def __init__(self):
        self.client = GeminiClient() if GeminiClient else None
        if not self.client:
            logger.error("GeminiClient not available. ReasoningEngine will fail.")
    
    def analyze(self, strategy_text: str, market_facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize Strategy + Facts -> Decision.
        
        Args:
            strategy_text: Natural language trading strategy
            market_facts: Dict of objective market observations
            
        Returns:
            Dict containing decision fields (bias, action, confidence, reasoning, etc.)
        """
        # Safety default - returned on any error
        default_decision = {
            "bias": "NEUTRAL",
            "reasoning": "Error in reasoning engine or connection.",
            "confidence": 0.0,
            "action": "WAIT",
            "blocking_factors": ["Reasoning engine error"]
        }

        if not self.client or not build_analysis_prompt:
            logger.error("Client or Prompt builder missing.")
            return default_decision

        try:
            # 1. Build Prompt
            prompt = build_analysis_prompt(strategy_text, market_facts)
            
            logger.debug(f"Generated prompt length: {len(prompt)} chars")
            
            # 2. Call LLM (with internal retry logic)
            response_json = self.client.generate_decision(prompt)
            
            if not response_json:
                logger.warning("Empty response from LLM")
                default_decision["reasoning"] = "LLM returned empty response"
                return default_decision
                
            # 3. Validate Schema
            try:
                decision = DecisionSchema(**response_json)
                result = decision.model_dump()
                
                # Log successful analysis
                logger.info(
                    f"LLM Analysis Complete: bias={result['bias']}, "
                    f"action={result['action']}, confidence={result['confidence']:.2f}"
                )
                
                return result
                
            except ValidationError as ve:
                logger.error(f"LLM Response Validation Failed: {ve}")
                logger.debug(f"Raw Response: {response_json}")
                
                # Try to extract what we can from the response
                return self._extract_partial_decision(response_json, default_decision)

        except Exception as e:
            logger.exception(f"Reasoning analysis failed: {e}")
            default_decision["reasoning"] = f"Analysis exception: {str(e)}"
            return default_decision
    
    def _extract_partial_decision(
        self, 
        response: Dict[str, Any], 
        default: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract what we can from a partially valid LLM response.
        
        This helps handle cases where the LLM returns mostly valid JSON
        but with some fields that don't match the schema.
        """
        result = default.copy()
        
        # Try to extract core fields
        if "bias" in response and response["bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]:
            result["bias"] = response["bias"]
        
        if "action" in response and response["action"] in ["TRADE", "MONITOR", "WAIT"]:
            result["action"] = response["action"]
        
        if "confidence" in response:
            try:
                conf = float(response["confidence"])
                result["confidence"] = max(0.0, min(1.0, conf))
            except (ValueError, TypeError):
                pass
        
        if "reasoning" in response and isinstance(response["reasoning"], str):
            result["reasoning"] = response["reasoning"]
        
        # Try to extract extended fields
        if "blocking_factors" in response and isinstance(response["blocking_factors"], list):
            result["blocking_factors"] = response["blocking_factors"]
        
        if "entry_conditions_met" in response and isinstance(response["entry_conditions_met"], list):
            result["entry_conditions_met"] = response["entry_conditions_met"]
        
        logger.warning(f"Extracted partial decision: bias={result['bias']}, action={result['action']}")
        return result

