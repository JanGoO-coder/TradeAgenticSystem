"""Agent Engine - Wrapper for the LangGraph ICT Trading Agent.

This module provides a clean interface to the existing agent,
treating it as a black-box core engine.
"""
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Add the source path to import the existing agent
# The agent code is in /agent/src, and graph.py imports from 'src.models'
# So we need to add /agent to path (for 'src.X' imports) 
# AND /agent/src to path (for direct 'graph' imports)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
AGENT_DIR = PROJECT_ROOT / "agent"
AGENT_SRC_DIR = AGENT_DIR / "src"

# Insert paths if not already present
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(AGENT_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC_DIR))


class TradingAgentEngine:
    """Wrapper for the ICT LangGraph trading agent."""
    
    def __init__(self):
        """Initialize the agent engine."""
        self._agent_available = False
        self._last_error: str = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Attempt to load the LangGraph agent."""
        try:
            from graph import run_analysis
            self._run_analysis = run_analysis
            self._agent_available = True
        except ImportError as e:
            self._last_error = f"Agent import error: {e}"
            self._agent_available = False
        except Exception as e:
            self._last_error = f"Agent initialization error: {e}"
            self._agent_available = False
    
    @property
    def is_available(self) -> bool:
        """Check if agent is available."""
        return self._agent_available
    
    @property
    def last_error(self) -> str:
        """Get last error message."""
        return self._last_error
    
    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run trade analysis on a market snapshot.
        
        Args:
            snapshot: Market snapshot matching the input contract
            
        Returns:
            Trade Setup Response
            
        Raises:
            RuntimeError: If agent is not available
        """
        if not self._agent_available:
            raise RuntimeError(f"Agent not available: {self._last_error}")
        
        try:
            result = self._run_analysis(snapshot)
            return result
        except Exception as e:
            raise RuntimeError(f"Agent analysis failed: {e}")
    
    def get_current_session(self, timestamp: datetime = None) -> Dict[str, Any]:
        """
        Get current session information.
        
        Args:
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Session information dict
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Import session detection from tools
        try:
            from tools import check_kill_zone, detect_session
            
            kz_result = check_kill_zone(timestamp)
            session = detect_session(timestamp)
            
            # Calculate EST time (UTC - 5)
            est_hour = (timestamp.hour - 5) % 24
            est_minute = timestamp.minute
            
            return {
                "session": session,
                "kill_zone_active": kz_result["in_kill_zone"],
                "kill_zone_name": kz_result.get("session"),
                "current_time_utc": timestamp.isoformat() + "Z",
                "current_time_est": f"{est_hour:02d}:{est_minute:02d}",
                "rule_refs": kz_result["rule_refs"]
            }
        except ImportError:
            # Fallback if tools not available
            return self._fallback_session_detection(timestamp)
    
    def _fallback_session_detection(self, timestamp: datetime) -> Dict[str, Any]:
        """Fallback session detection without importing tools."""
        hour_utc = timestamp.hour
        est_hour = (hour_utc - 5) % 24
        
        # Simple session detection
        if 7 <= hour_utc < 10:  # London KZ
            session = "London"
            in_kz = True
            kz_name = "London"
        elif 12 <= hour_utc < 15:  # NY KZ
            session = "NY"
            in_kz = True
            kz_name = "NY"
        elif 3 <= hour_utc < 8:
            session = "London"
            in_kz = False
            kz_name = None
        elif 8 <= hour_utc < 17:
            session = "NY"
            in_kz = False
            kz_name = None
        else:
            session = "Asia"
            in_kz = False
            kz_name = None
        
        return {
            "session": session,
            "kill_zone_active": in_kz,
            "kill_zone_name": kz_name,
            "current_time_utc": timestamp.isoformat() + "Z",
            "current_time_est": f"{est_hour:02d}:{timestamp.minute:02d}",
            "rule_refs": ["8.1"]
        }


# Singleton instance
_agent_engine: TradingAgentEngine = None


def get_agent_engine() -> TradingAgentEngine:
    """Get or create the agent engine singleton."""
    global _agent_engine
    if _agent_engine is None:
        _agent_engine = TradingAgentEngine()
    return _agent_engine
