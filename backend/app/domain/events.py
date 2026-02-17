"""
Market Events - Factual event emissions from the Observer.

Events are FACTS, not interpretations. The event says WHAT happened,
not WHAT IT MEANS. Interpretation happens in the Agent using Context.

Example:
✅ Good: "Liquidity sweep: sell-side at 1.0820 taken at 10:32"
❌ Bad: "Bullish setup forming"
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict


class EventType(Enum):
    """Types of market events the observer can emit."""
    
    # =========================================================================
    # Structure Events (ICT Rules 2.x)
    # =========================================================================
    SWING_HIGH_FORMED = "swing_high_formed"
    SWING_LOW_FORMED = "swing_low_formed"
    BOS_BULLISH = "bos_bullish"           # Break of structure bullish
    BOS_BEARISH = "bos_bearish"           # Break of structure bearish
    MSS_BULLISH = "mss_bullish"           # Market structure shift bullish
    MSS_BEARISH = "mss_bearish"           # Market structure shift bearish
    DEALING_RANGE_FORMED = "dealing_range_formed"
    
    # =========================================================================
    # Liquidity Events (ICT Rules 3.x)
    # =========================================================================
    LIQUIDITY_SWEEP_BUYSIDE = "sweep_buyside"
    LIQUIDITY_SWEEP_SELLSIDE = "sweep_sellside"
    EQUAL_HIGHS_FORMED = "equal_highs"
    EQUAL_LOWS_FORMED = "equal_lows"
    INDUCEMENT_DETECTED = "inducement"
    STOP_HUNT = "stop_hunt"
    LIQUIDITY_VOID_FORMED = "liquidity_void"
    
    # =========================================================================
    # PD Array Events (ICT Rules 5.x)
    # =========================================================================
    FVG_BULLISH_FORMED = "fvg_bullish"
    FVG_BEARISH_FORMED = "fvg_bearish"
    FVG_MITIGATED = "fvg_mitigated"
    OB_BULLISH_FORMED = "ob_bullish"
    OB_BEARISH_FORMED = "ob_bearish"
    OB_MITIGATED = "ob_mitigated"
    BREAKER_FORMED = "breaker_formed"
    MITIGATION_BLOCK_FORMED = "mitigation_block"
    BPR_FORMED = "bpr_formed"  # Balanced Price Range
    
    # =========================================================================
    # Displacement Events
    # =========================================================================
    DISPLACEMENT_BULLISH = "displacement_bullish"
    DISPLACEMENT_BEARISH = "displacement_bearish"
    
    # =========================================================================
    # Session Events (ICT Rules 8.x)
    # =========================================================================
    SESSION_OPENED = "session_opened"
    SESSION_CLOSED = "session_closed"
    KILLZONE_ENTERED = "killzone_entered"
    KILLZONE_EXITED = "killzone_exited"
    NEWS_COOLDOWN_STARTED = "news_cooldown_start"
    NEWS_COOLDOWN_ENDED = "news_cooldown_end"
    
    # =========================================================================
    # Price Level Events
    # =========================================================================
    PRICE_ENTERED_PREMIUM = "entered_premium"
    PRICE_ENTERED_DISCOUNT = "entered_discount"
    PRICE_ENTERED_EQUILIBRIUM = "entered_equilibrium"
    PRICE_ENTERED_OTE = "entered_ote"
    PRICE_EXITED_OTE = "exited_ote"
    
    # =========================================================================
    # Entry Pattern Events (ICT Rules 6.x)
    # =========================================================================
    OTE_ZONE_REACHED = "ote_zone_reached"
    SWEEP_DISP_FVG_SEQUENCE = "sweep_disp_fvg"
    ICT_2022_MODEL_DETECTED = "ict_2022_model"
    TURTLE_SOUP_DETECTED = "turtle_soup"
    PO3_PHASE_CHANGED = "po3_phase_changed"


@dataclass
class MarketEvent:
    """
    A single, factual market event.
    
    Events are FACTS, not interpretations.
    The event says WHAT happened, not WHAT IT MEANS.
    """
    
    type: EventType
    timestamp: datetime
    symbol: str
    
    # Event-specific data (factual only)
    price: Optional[float] = None
    price_level: Optional[float] = None  # The level involved
    candle_index: Optional[int] = None   # Which candle triggered this
    timeframe: Optional[str] = None      # e.g., "1H", "15M", "5M"
    
    # Factual description (no interpretation)
    description: str = ""
    
    # Raw data for audit trail
    raw_data: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Event ID for deduplication
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            # Generate unique event ID
            import hashlib
            content = f"{self.type.value}:{self.timestamp.isoformat()}:{self.symbol}:{self.price_level}"
            self.event_id = hashlib.md5(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "price": self.price,
            "price_level": self.price_level,
            "candle_index": self.candle_index,
            "timeframe": self.timeframe,
            "description": self.description
        }
    
    def __str__(self) -> str:
        """Format event as factual log line."""
        time_str = self.timestamp.strftime('%H:%M')
        level_str = f" @ {self.price_level:.5f}" if self.price_level else ""
        return f"[{time_str}] {self.type.value}{level_str}: {self.description}"
    
    def __repr__(self) -> str:
        return f"MarketEvent({self.type.value}, {self.timestamp.strftime('%H:%M')}, {self.description[:30]}...)"


@dataclass
class EventBatch:
    """
    Collection of events from a single observation cycle.
    """
    
    symbol: str
    observation_timestamp: datetime
    events: list[MarketEvent] = field(default_factory=list)
    
    def add(self, event: MarketEvent):
        """Add an event to the batch."""
        self.events.append(event)
    
    def get_by_type(self, event_type: EventType) -> list[MarketEvent]:
        """Filter events by type."""
        return [e for e in self.events if e.type == event_type]
    
    def has_event(self, event_type: EventType) -> bool:
        """Check if an event type exists in batch."""
        return any(e.type == event_type for e in self.events)
    
    def to_log(self, max_events: int = 20) -> str:
        """Format events as a factual log for the LLM."""
        lines = [
            f"## Market Events: {self.symbol}",
            f"**Time**: {self.observation_timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Events Count**: {len(self.events)}",
            "",
            "### Event Log (Most Recent First)",
            ""
        ]
        
        for event in reversed(self.events[-max_events:]):
            lines.append(f"- {event}")
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self.events)
