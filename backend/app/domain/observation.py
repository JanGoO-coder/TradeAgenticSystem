"""
Observation Result - Event-based observer output.

Observer outputs FACTS, not interpretations.
Events are what happened. The Agent interprets their meaning.

Example:
✅ Good: "BOS detected: price closed above 1.0850 swing high"
❌ Bad: "Bullish setup forming"
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import hashlib

from app.domain.events import MarketEvent, EventType, EventBatch


@dataclass
class ObservationResult:
    """
    Observer output: Events + Raw Data.
    
    No interpretations. Just facts.
    This is what the Observer returns after analyzing market data.
    """
    
    symbol: str
    timestamp: datetime
    current_price: float
    
    # Emitted events (factual)
    events: List[MarketEvent] = field(default_factory=list)
    
    # Raw analytical data (for context manager to process)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    # State hash for change detection
    state_hash: str = ""
    
    def __post_init__(self):
        if not self.state_hash:
            self._compute_state_hash()
    
    def _compute_state_hash(self):
        """Compute hash of key state for change detection."""
        key_data = (
            f"{self.symbol}:"
            f"{self.current_price:.5f}:"
            f"{self.raw_data.get('htf_bias', {}).get('bias', '')}:"
            f"{len(self.raw_data.get('fvgs', []))}:"
            f"{len(self.raw_data.get('sweeps', []))}:"
            f"{self.raw_data.get('killzone', {}).get('in_killzone', False)}"
        )
        self.state_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def get_events_by_type(self, event_type: EventType) -> List[MarketEvent]:
        """Filter events by type."""
        return [e for e in self.events if e.type == event_type]
    
    def get_recent_events(self, minutes: int = 30) -> List[MarketEvent]:
        """Get events from last N minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [e for e in self.events if e.timestamp > cutoff]
    
    def has_event(self, event_type: EventType) -> bool:
        """Check if a specific event type occurred."""
        return any(e.type == event_type for e in self.events)
    
    def to_event_log(self, max_events: int = 20) -> str:
        """Format events as a factual log for the LLM."""
        lines = [
            f"## Market Events: {self.symbol}",
            f"**Time**: {self.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Price**: {self.current_price:.5f}",
            "",
            "### Event Log (Most Recent First)",
            ""
        ]
        
        for event in reversed(self.events[-max_events:]):
            lines.append(f"- {event}")
        
        if not self.events:
            lines.append("- No significant events detected")
        
        return "\n".join(lines)
    
    def to_summary(self) -> str:
        """
        Generate ICT-focused observation summary.
        
        This replaces the old MarketObservation.to_summary() with
        a more dynamic, event-driven format.
        """
        parts = [
            f"# ICT Market Observation: {self.symbol}",
            f"**Time**: {self.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Price**: {self.current_price:.5f}",
            f"**State Hash**: {self.state_hash}",
            "",
        ]
        
        # 1. MARKET FRAMEWORK (Rules 1.x)
        parts.extend(self._format_market_framework())
        
        # 2. LIQUIDITY STATUS (Rules 3.x)
        parts.extend(self._format_liquidity_status())
        
        # 3. PD ARRAYS (Rules 5.x)
        parts.extend(self._format_pd_arrays())
        
        # 4. SESSION CONTEXT (Rules 8.x)
        parts.extend(self._format_session_context())
        
        # 5. DETECTED ENTRY MODELS (Rules 6.x)
        parts.extend(self._format_entry_models())
        
        # 6. EXECUTION CHECKLIST (Rule 10)
        parts.extend(self._format_checklist())
        
        # 7. EVENT LOG
        parts.extend([
            "",
            self.to_event_log(max_events=15)
        ])
        
        return "\n".join(parts)
    
    def _format_market_framework(self) -> List[str]:
        """Format market framework section."""
        htf_bias = self.raw_data.get("htf_bias", {})
        ltf_alignment = self.raw_data.get("ltf_alignment", {})
        mss = self.raw_data.get("mss")
        htf_structure = self.raw_data.get("htf_structure", {})
        
        bias = htf_bias.get("bias", "UNKNOWN")
        bias_icon = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "⚪"
        
        aligned = ltf_alignment.get("aligned", False)
        aligned_icon = "✅" if aligned else "❌"
        
        lines = [
            "## 1. Market Framework",
            f"**HTF Bias**: {bias_icon} {bias}",
            f"**LTF Aligned**: {aligned_icon} {aligned}",
            f"**Structure**: {htf_structure.get('structure', 'UNKNOWN')}",
        ]
        
        if mss:
            mss_type = mss.get("type", "unknown")
            mss_level = mss.get("broken_level", 0)
            lines.append(f"**MSS**: {mss_type.upper()} at {mss_level:.5f}")
        
        lines.append("")
        return lines
    
    def _format_liquidity_status(self) -> List[str]:
        """Format liquidity section."""
        sweeps = self.raw_data.get("sweeps", [])
        equal_levels = self.raw_data.get("equal_levels", {})
        
        lines = [
            "## 3. Liquidity Status",
            f"**Recent Sweeps**: {len(sweeps)}",
        ]
        
        if sweeps:
            last_sweep = sweeps[-1]
            lines.append(f"**Last Sweep**: {last_sweep.get('type', 'unknown')} at {last_sweep.get('level', 0):.5f}")
        
        if equal_levels.get("highs"):
            lines.append(f"**Equal Highs**: {len(equal_levels['highs'])} targets")
        
        if equal_levels.get("lows"):
            lines.append(f"**Equal Lows**: {len(equal_levels['lows'])} targets")
        
        lines.append("")
        return lines
    
    def _format_pd_arrays(self) -> List[str]:
        """Format PD arrays section."""
        pd_zone = self.raw_data.get("premium_discount", {})
        fvgs = self.raw_data.get("fvgs", [])
        order_blocks = self.raw_data.get("order_blocks", [])
        ote = self.raw_data.get("ote")
        
        zone = pd_zone.get("zone", "UNKNOWN")
        zone_pct = pd_zone.get("percentage", 0.5)
        zone_icon = "🔺" if zone == "PREMIUM" else "🔻" if zone == "DISCOUNT" else "⚖️"
        
        unfilled_fvgs = [f for f in fvgs if not f.get("filled")]
        
        lines = [
            "## 5. PD Arrays",
            f"**Zone**: {zone_icon} {zone} ({zone_pct:.0%})",
            f"**Unfilled FVGs**: {len(unfilled_fvgs)}",
            f"**Order Blocks**: {len(order_blocks)}",
        ]
        
        if ote:
            in_ote = ote.get("lower", 0) <= self.current_price <= ote.get("upper", 0)
            ote_icon = "✅" if in_ote else "❌"
            lines.append(f"**OTE Zone**: {ote_icon} {ote.get('lower', 0):.5f} - {ote.get('upper', 0):.5f}")
        
        # List top 3 FVGs
        if unfilled_fvgs[:3]:
            lines.append("**Active FVGs**:")
            for fvg in unfilled_fvgs[:3]:
                fvg_type = fvg.get("type", "unknown")
                lines.append(f"  - {fvg_type}: {fvg.get('low', 0):.5f} - {fvg.get('high', 0):.5f}")
        
        lines.append("")
        return lines
    
    def _format_session_context(self) -> List[str]:
        """Format session section."""
        session = self.raw_data.get("session", {})
        killzone = self.raw_data.get("killzone", {})
        po3 = self.raw_data.get("power_of_three", {})
        
        in_kz = killzone.get("in_killzone", False)
        kz_icon = "✅" if in_kz else "❌"
        
        lines = [
            "## 8. Session Context",
            f"**Session**: {session.get('session', 'UNKNOWN')}",
            f"**Killzone**: {kz_icon} {killzone.get('session', 'None') if in_kz else 'Not in killzone'}",
            f"**PO3 Phase**: {po3.get('phase', 'UNKNOWN')}",
            ""
        ]
        return lines
    
    def _format_entry_models(self) -> List[str]:
        """Detect and format potential entry models."""
        models = []
        
        # Get observation data
        mss = self.raw_data.get("mss")
        ote = self.raw_data.get("ote")
        sweeps = self.raw_data.get("sweeps", [])
        displacements = self.raw_data.get("displacements", [])
        fvgs = [f for f in self.raw_data.get("fvgs", []) if not f.get("filled")]
        ltf_aligned = self.raw_data.get("ltf_alignment", {}).get("aligned", False)
        
        # 6.1 OTE Entry
        if ote and mss:
            in_ote = ote.get("lower", 0) <= self.current_price <= ote.get("upper", 0)
            if in_ote:
                models.append(("OTE Entry", "6.1", "MSS + price in OTE zone"))
        
        # 6.2 FVG Entry
        if fvgs and ltf_aligned:
            models.append(("FVG Entry", "6.2", f"{len(fvgs)} unfilled FVGs"))
        
        # 6.3 Sweep → Displacement → FVG
        if sweeps and displacements and fvgs:
            models.append(("Sweep→Disp→FVG", "6.3", "Full sequence detected"))
        
        # 6.5 ICT 2022 Model (requires all elements)
        if self._check_ict_2022_confluence():
            models.append(("ICT 2022 Model", "6.5", "All elements aligned"))
        
        # Format output
        if not models:
            return [
                "## 6. Entry Models",
                "No entry models currently detected",
                ""
            ]
        
        lines = [
            "## 6. Detected Entry Models",
        ]
        for name, rule, status in models:
            lines.append(f"- **{name}** (Rule {rule}): {status}")
        lines.append("")
        
        return lines
    
    def _check_ict_2022_confluence(self) -> bool:
        """Check if ICT 2022 model confluence exists."""
        htf_bias_clear = self.raw_data.get("htf_bias", {}).get("bias") != "NEUTRAL"
        ltf_aligned = self.raw_data.get("ltf_alignment", {}).get("aligned", False)
        has_sweep = len(self.raw_data.get("sweeps", [])) > 0
        has_displacement = len(self.raw_data.get("displacements", [])) > 0
        has_fvg = any(not f.get("filled") for f in self.raw_data.get("fvgs", []))
        in_killzone = self.raw_data.get("killzone", {}).get("in_killzone", False)
        
        return all([htf_bias_clear, ltf_aligned, has_sweep, has_displacement, has_fvg, in_killzone])
    
    def _format_checklist(self) -> List[str]:
        """Format execution checklist (Rule 10)."""
        checks = [
            ("HTF Bias Clear", self.raw_data.get("htf_bias", {}).get("bias") != "NEUTRAL"),
            ("LTF MSS/Aligned", 
             self.raw_data.get("mss") is not None or 
             self.raw_data.get("ltf_alignment", {}).get("aligned", False)),
            ("PD Zone Correct", self._is_pd_zone_valid()),
            ("Liquidity Swept", len(self.raw_data.get("sweeps", [])) > 0),
            ("Displacement", len(self.raw_data.get("displacements", [])) > 0),
            ("Killzone Active", self.raw_data.get("killzone", {}).get("in_killzone", False)),
        ]
        
        passed = sum(1 for _, ok in checks if ok)
        total = len(checks)
        
        lines = [
            "## 10. Execution Checklist",
            f"**Score: {passed}/{total}**",
            ""
        ]
        
        for name, ok in checks:
            icon = "✅" if ok else "❌"
            lines.append(f"{icon} {name}")
        
        lines.append("")
        return lines
    
    def _is_pd_zone_valid(self) -> bool:
        """Check if PD zone is valid for potential entry."""
        zone = self.raw_data.get("premium_discount", {}).get("zone", "EQUILIBRIUM")
        bias = self.raw_data.get("htf_bias", {}).get("bias", "NEUTRAL")
        
        # LONG should be in DISCOUNT, SHORT in PREMIUM
        if bias == "BULLISH" and zone == "DISCOUNT":
            return True
        if bias == "BEARISH" and zone == "PREMIUM":
            return True
        if zone == "EQUILIBRIUM":
            return True  # Acceptable
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "state_hash": self.state_hash,
            "events_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
            "raw_data": self.raw_data
        }
