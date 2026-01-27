"""
Gemini Client for Neuro-Symbolic Agent.

Uses the new google.genai SDK (GA as of May 2025) for accessing Gemini models.
Replaces the deprecated google.generativeai package.
"""
import os
import logging
import json
import time
from typing import Dict, Any, Optional

# New unified SDK import
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google Gemini LLM using the new google.genai SDK.
    
    Features:
    - Configured for JSON output
    - Low temperature for deterministic behavior
    - Retry logic with exponential backoff
    - Error classification and logging
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 1.0  # seconds
    
    # Model name (Gemini 2.5 Flash)
    MODEL_NAME = "gemini-2.5-flash"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not found. LLM calls will fail.")
            self.client = None
        else:
            # Initialize the new genai Client with API key
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini Client initialized with model: {self.MODEL_NAME}")
        
    def generate_decision(self, prompt: str, retries: int = 0) -> Dict[str, Any]:
        """
        Send a prompt to Gemini and expect a valid JSON response.
        
        Implements retry logic for transient failures.
        
        Args:
            prompt: The formatted prompt to send
            retries: Current retry count (used internally for recursion)
            
        Returns:
            Dict containing the parsed JSON response, or empty dict on failure
        """
        if not self.client:
            logger.error("Gemini Client not initialized (missing API key).")
            return {}
            
        try:
            # Configure generation for JSON output with low temperature
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1  # Low temperature for deterministic behavior
            )
            
            # Generate content using the new SDK
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=prompt,
                config=config
            )
            
            # Check for safety blocks
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    # Check if blocked by safety
                    if finish_reason and str(finish_reason).upper() in ['SAFETY', 'BLOCKED']:
                        logger.warning(f"Response blocked by safety filter: {finish_reason}")
                        return {}
            
            # Extract text from response
            response_text = response.text if hasattr(response, 'text') else None
            
            if response_text:
                try:
                    result = json.loads(response_text)
                    logger.debug(f"LLM response received: {len(response_text)} chars")
                    return result
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to parse LLM JSON response: {je}")
                    logger.debug(f"Raw response: {response_text[:500]}...")
                    
                    # Retry on JSON parse error (LLM might produce better output)
                    if retries < self.MAX_RETRIES:
                        return self._retry(prompt, retries, "JSON parse error")
                    return {}
            else:
                logger.warning("Empty response text from Gemini")
                
                # Retry on empty response
                if retries < self.MAX_RETRIES:
                    return self._retry(prompt, retries, "Empty response")
                return {}
                
        except Exception as e:
            error_msg = str(e)
            
            # Classify error type
            is_transient = self._is_transient_error(error_msg)
            
            if is_transient and retries < self.MAX_RETRIES:
                return self._retry(prompt, retries, error_msg)
            
            logger.exception(f"Gemini API call failed permanently: {e}")
            return {}
    
    def _retry(self, prompt: str, current_retry: int, reason: str) -> Dict[str, Any]:
        """
        Execute a retry with exponential backoff.
        
        Args:
            prompt: The prompt to retry
            current_retry: Current retry count
            reason: Reason for the retry (for logging)
            
        Returns:
            Dict from the retried call
        """
        delay = self.BASE_RETRY_DELAY * (current_retry + 1)
        logger.warning(
            f"Retrying LLM call (attempt {current_retry + 2}/{self.MAX_RETRIES + 1}) "
            f"after {delay}s. Reason: {reason}"
        )
        time.sleep(delay)
        return self.generate_decision(prompt, retries=current_retry + 1)
    
    def _is_transient_error(self, error_msg: str) -> bool:
        """
        Check if an error is likely transient and worth retrying.
        
        Args:
            error_msg: The error message string
            
        Returns:
            True if the error appears to be transient
        """
        transient_indicators = [
            "timeout",
            "timed out",
            "rate limit",
            "429",
            "503",
            "502",
            "server error",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "overloaded",
            "quota",
            "resource_exhausted"
        ]
        
        error_lower = error_msg.lower()
        return any(indicator in error_lower for indicator in transient_indicators)


