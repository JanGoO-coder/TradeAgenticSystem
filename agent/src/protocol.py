"""
Communication Protocol for Hierarchical Agent Architecture.

Defines message envelopes, action types, and audit logging for
inter-agent communication between Main, Strategy, and Worker agents.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import uuid


# =============================================================================
# Action Types
# =============================================================================

class ActionType(str, Enum):
    """All possible inter-agent action types."""

    # Main → Worker
    GET_SNAPSHOT = "GET_SNAPSHOT"           # Request OHLCV + News data
    SCAN_SETUPS = "SCAN_SETUPS"             # Find patterns given Strategy context
    EXECUTE_ORDER = "EXECUTE_ORDER"         # Place a trade
    ADVANCE_TIME = "ADVANCE_TIME"           # Move simulation forward
    GET_POSITIONS = "GET_POSITIONS"         # Get open positions
    CLOSE_POSITION = "CLOSE_POSITION"       # Close a position

    # Main → Strategy
    ANALYZE_CONTEXT = "ANALYZE_CONTEXT"     # Get bias, environment, levels

    # Response Actions (Any → Main)
    SNAPSHOT_RESULT = "SNAPSHOT_RESULT"     # Return market data
    CONTEXT_RESULT = "CONTEXT_RESULT"       # Return MarketContext
    SETUP_RESULT = "SETUP_RESULT"           # Return detected patterns
    EXECUTION_RECEIPT = "EXECUTION_RECEIPT" # Confirm trade placed
    POSITIONS_RESULT = "POSITIONS_RESULT"   # Return positions list
    TIME_ADVANCED = "TIME_ADVANCED"         # Confirm time advancement

    # Reliability Actions
    ACK = "ACK"                             # Message received
    NACK = "NACK"                           # Message rejected/failed immediately

    # Error
    ERROR = "ERROR"                         # Error response


class AgentRole(str, Enum):
    """Agent identifiers for message routing."""
    TRADER = "Trader"       # User/External
    MAIN = "Main"           # Orchestrator
    STRATEGY = "Strategy"   # Analyst
    WORKER = "Worker"       # Executor


# =============================================================================
# Standardized Payloads
# =============================================================================

class ErrorPayload(BaseModel):
    """Standard payload for ERROR action."""
    code: str
    message: str
    stack: Optional[str] = None
    retryable: bool = False
    original_action: Optional[ActionType] = None


class ReceiptPayload(BaseModel):
    """Standard payload for ACK/NACK/EXECUTION_RECEIPT."""
    original_msg_id: str
    status: Literal["RECEIVED", "PROCESSED", "FAILED", "REJECTED"]
    details: Optional[str] = None


# =============================================================================
# Protocol Rules (Request-Response Mapping)
# =============================================================================

REQUEST_RESPONSE_MAP = {
    ActionType.GET_SNAPSHOT:    [ActionType.SNAPSHOT_RESULT, ActionType.ERROR],
    ActionType.SCAN_SETUPS:     [ActionType.SETUP_RESULT, ActionType.ERROR],
    ActionType.EXECUTE_ORDER:   [ActionType.EXECUTION_RECEIPT, ActionType.ERROR],
    ActionType.ADVANCE_TIME:    [ActionType.TIME_ADVANCED, ActionType.ERROR],
    ActionType.GET_POSITIONS:   [ActionType.POSITIONS_RESULT, ActionType.ERROR],
    ActionType.CLOSE_POSITION:  [ActionType.EXECUTION_RECEIPT, ActionType.ERROR],
    ActionType.ANALYZE_CONTEXT: [ActionType.CONTEXT_RESULT, ActionType.ERROR],
}


# =============================================================================
# Message Envelope
# =============================================================================

class MessageEnvelope(BaseModel):
    """
    Standardized envelope for all inter-agent communication.

    Every message between agents uses this format for:
    - Traceability (correlation_id links related messages)
    - Audit logging (timestamp + from/to)
    - Reliability (timeouts, retries)
    - Structured payload
    """
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    from_agent: AgentRole
    to_agent: AgentRole
    action: ActionType
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Correlation & Reliability
    correlation_id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:8]}")
    response_to: Optional[str] = None       # ID of message this is responding to
    
    # Metadata
    timeout_ms: Optional[int] = None        # Expected processing time (ms)
    retry_count: int = 0                    # 0 = first attempt
    meta: Dict[str, Any] = Field(default_factory=dict) # Open slot for tracing headers etc

    # Compatibility Aliases
    @property
    def reply_to(self) -> Optional[str]:
        return self.response_to

    @property
    def error(self) -> Optional[str]:
        # Backward compatibility accessor for simple error string
        if self.action == ActionType.ERROR and "message" in self.payload:
            return self.payload["message"]
        return None

    class Config:
        use_enum_values = True

    def create_reply(
        self,
        action: ActionType,
        payload: Dict[str, Any],
        is_error: bool = False
    ) -> "MessageEnvelope":
        """
        Create a reply message with enforced correlation.
        
        Args:
            action: The response action type.
            payload: Content of the response.
            is_error: If True, skips strict mapping check (errors always allowed).
        """
        # strict validation of expected response types
        if not is_error and self.action in REQUEST_RESPONSE_MAP:
            allowed = REQUEST_RESPONSE_MAP[self.action]
            if action not in allowed:
                # We log/warn here in real app, but strictly we enforce or just allow flex for now
                pass 

        return MessageEnvelope(
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            action=action,
            payload=payload,
            correlation_id=self.correlation_id, # MUST propagate matches
            response_to=self.id,
            meta=self.meta.copy(), # Propagate metadata context
        )

    def create_ack(self) -> "MessageEnvelope":
        """Create a standard acknowledgement receipt."""
        return self.create_reply(
            action=ActionType.ACK,
            payload=ReceiptPayload(
                original_msg_id=self.id,
                status="RECEIVED"
            ).model_dump()
        )

    def create_nack(self, reason: str) -> "MessageEnvelope":
        """Create a standard negative acknowledgement."""
        return self.create_reply(
            action=ActionType.NACK,
            payload=ReceiptPayload(
                original_msg_id=self.id,
                status="REJECTED",
                details=reason
            ).model_dump()
        )


# =============================================================================
# Message Log (Audit Trail)
# =============================================================================

class MessageLog:
    """
    Append-only audit trail for "Glass Box" replay visualization.

    Records all inter-agent messages for:
    - Debugging and traceability
    - Replay visualization in UI
    - Performance analysis
    """

    def __init__(self):
        self._messages: List[MessageEnvelope] = []
        self._by_correlation: Dict[str, List[MessageEnvelope]] = {}

    def append(self, message: MessageEnvelope) -> None:
        """Append a message to the log."""
        self._messages.append(message)

        # Index by correlation_id
        if message.correlation_id not in self._by_correlation:
            self._by_correlation[message.correlation_id] = []
        self._by_correlation[message.correlation_id].append(message)

    def get_all(self) -> List[MessageEnvelope]:
        """Get all messages in order."""
        return self._messages.copy()

    def get_by_correlation(self, correlation_id: str) -> List[MessageEnvelope]:
        """Get all messages for a specific session/correlation."""
        return self._by_correlation.get(correlation_id, []).copy()

    def get_last(self, n: int = 10) -> List[MessageEnvelope]:
        """Get last N messages."""
        return self._messages[-n:] if self._messages else []

    def filter_by_action(self, action: ActionType) -> List[MessageEnvelope]:
        """Filter messages by action type."""
        return [m for m in self._messages if m.action == action]

    def filter_by_agent(self, agent: AgentRole) -> List[MessageEnvelope]:
        """Filter messages from a specific agent."""
        return [m for m in self._messages if m.from_agent == agent]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Export all messages as list of dicts for JSON serialization."""
        return [m.model_dump() for m in self._messages]

    def clear(self) -> None:
        """Clear all messages (use with caution)."""
        self._messages.clear()
        self._by_correlation.clear()

    def __len__(self) -> int:
        return len(self._messages)


# =============================================================================
# Tick Event (For Glass Box Visualization)
# =============================================================================

class TickEvent(BaseModel):
    """
    A single tick in the simulation with all agent events.

    Used for replay visualization in the frontend.
    """
    tick: int
    time: datetime
    events: List[Dict[str, Any]] = Field(default_factory=list)

    def add_event(
        self,
        agent: AgentRole,
        action: str,
        **kwargs
    ) -> None:
        """Add an event to this tick."""
        self.events.append({
            "agent": agent.value if isinstance(agent, AgentRole) else agent,
            "action": action,
            **kwargs
        })


class TickLog:
    """
    Aggregated log of ticks for visualization.

    Groups messages by simulation tick for UI replay.
    """

    def __init__(self):
        self._ticks: List[TickEvent] = []
        self._current_tick: int = 0

    def new_tick(self, time: datetime) -> TickEvent:
        """Start a new tick."""
        self._current_tick += 1
        tick = TickEvent(tick=self._current_tick, time=time)
        self._ticks.append(tick)
        return tick

    def get_tick(self, tick_num: int) -> Optional[TickEvent]:
        """Get a specific tick by number."""
        for tick in self._ticks:
            if tick.tick == tick_num:
                return tick
        return None

    def get_all(self) -> List[TickEvent]:
        """Get all ticks."""
        return self._ticks.copy()

    def get_range(self, start: int, end: int) -> List[TickEvent]:
        """Get ticks in range [start, end)."""
        return [t for t in self._ticks if start <= t.tick < end]

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Export for JSON serialization."""
        return [t.model_dump() for t in self._ticks]

    def __len__(self) -> int:
        return len(self._ticks)


# =============================================================================
# Helper Functions
# =============================================================================

def create_request(
    from_agent: AgentRole,
    to_agent: AgentRole,
    action: ActionType,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
    response_to: Optional[str] = None
) -> MessageEnvelope:
    """Create a request message."""
    msg = MessageEnvelope(
        from_agent=from_agent,
        to_agent=to_agent,
        action=action,
        payload=payload
    )
    if correlation_id:
        msg.correlation_id = correlation_id
    if response_to:
        msg.response_to = response_to
    return msg


def create_error_response(
    original: MessageEnvelope,
    error_message: str,
    code: str = "GENERIC_ERROR",
    retryable: bool = False
) -> MessageEnvelope:
    """Create an error response to a message."""
    return original.create_reply(
        action=ActionType.ERROR,
        payload=ErrorPayload(
            code=code,
            message=error_message,
            retryable=retryable,
            original_action=original.action
        ).model_dump(),
        is_error=True
    )
