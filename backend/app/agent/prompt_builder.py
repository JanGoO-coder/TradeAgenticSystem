"""
ICT Prompt Builder - Dynamic prompt generation from ICT Rulebook.

This is the PROMPT COMPILATION layer. It:
1. Parses the ICT Rulebook into structured rules
2. Builds system prompts dynamically from those rules
3. Injects current market context into prompts

This allows:
- Strategy swapping without code changes
- Same agent → different market styles
- Deterministic reasoning prompts
"""
import re
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.services.market_context import MarketContext


class ICTPromptBuilder:
    """
    Builds dynamic prompts from ICT Rulebook.
    
    Parses the rulebook markdown file and generates
    system prompts with context injection.
    """
    
    # ICT Rulebook section mapping
    SECTIONS = {
        "market_framework": ["1.1", "1.1.1", "1.1.2", "1.2", "1.2.1", "1.2.2", "1.2.3"],
        "directional_bias": ["2.1", "2.2", "2.3", "2.4"],
        "liquidity": ["3.1", "3.2", "3.3", "3.4", "3.5"],
        "price_delivery": ["4.1", "4.2"],
        "pd_arrays": ["5.1", "5.2", "5.3", "5.4", "5.5", "5.6"],
        "entry_models": ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7"],
        "risk_management": ["7.1", "7.2", "7.3", "7.4", "7.5", "7.6"],
        "session_time": ["8.1", "8.2", "8.3", "8.4"],
        "invalidation": ["9.1", "9.2", "9.3"],
        "execution_checklist": ["10"],
        "common_patterns": ["11"],
        "governance": ["12"]
    }
    
    def __init__(self, rulebook_path: Optional[str] = None):
        """
        Initialize prompt builder.
        
        Args:
            rulebook_path: Path to ICT rulebook markdown file.
                          If None, uses default path.
        """
        if rulebook_path is None:
            # Default path relative to project
            rulebook_path = Path(__file__).parent.parent.parent.parent / "rules" / "rules" / "ICT_Rulebook_V1.md"
        
        self.rulebook_path = Path(rulebook_path)
        self._parsed_rules: Dict[str, Dict[str, Any]] = {}
        self._rulebook_loaded = False
        
        # Try to load rulebook
        if self.rulebook_path.exists():
            self._load_rulebook()
    
    def _load_rulebook(self):
        """Parse ICT rulebook into structured rules."""
        try:
            content = self.rulebook_path.read_text(encoding="utf-8")
            self._parse_rulebook_content(content)
            self._rulebook_loaded = True
        except Exception as e:
            print(f"Warning: Could not load ICT rulebook: {e}")
            self._rulebook_loaded = False
    
    def _parse_rulebook_content(self, content: str):
        """Parse rulebook markdown content into structured rules."""
        current_rule_id = None
        current_rule = None
        
        for line in content.split("\n"):
            line = line.strip()
            
            # Detect section headers (### X.X Title or ## X.X Title)
            header_match = re.match(r'^#{2,4}\s+(\d+\.?\d*\.?\d*)\s+(.+)$', line)
            if header_match:
                # Save previous rule if exists
                if current_rule_id and current_rule:
                    self._parsed_rules[current_rule_id] = current_rule
                
                rule_id = header_match.group(1).strip()
                rule_title = header_match.group(2).strip()
                
                current_rule_id = rule_id
                current_rule = {
                    "id": rule_id,
                    "title": rule_title,
                    "what": "",
                    "why": "",
                    "when_valid": "",
                    "when_invalid": "",
                    "full_text": ""
                }
            elif current_rule:
                # Parse What/Why/When fields
                lower_line = line.lower()
                
                if lower_line.startswith("what:") or lower_line.startswith("**what:**"):
                    current_rule["what"] = self._extract_value(line, "what")
                elif lower_line.startswith("why:") or lower_line.startswith("**why:**"):
                    current_rule["why"] = self._extract_value(line, "why")
                elif "when valid:" in lower_line or "**when:**" in lower_line:
                    current_rule["when_valid"] = self._extract_after_colon(line)
                elif "when invalid:" in lower_line or "**when not:**" in lower_line:
                    current_rule["when_invalid"] = self._extract_after_colon(line)
                
                # Accumulate full text
                if line:
                    current_rule["full_text"] += line + " "
        
        # Save last rule
        if current_rule_id and current_rule:
            self._parsed_rules[current_rule_id] = current_rule
    
    def _extract_value(self, line: str, key: str) -> str:
        """Extract value after a key like 'What:' or '**What:**'"""
        patterns = [
            f"{key}:",
            f"**{key}:**",
            f"**{key.capitalize()}:**"
        ]
        for pattern in patterns:
            if pattern.lower() in line.lower():
                return line.split(":", 1)[-1].strip()
        return ""
    
    def _extract_after_colon(self, line: str) -> str:
        """Extract everything after the first colon."""
        if ":" in line:
            return line.split(":", 1)[-1].strip()
        return line
    
    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific rule by ID."""
        return self._parsed_rules.get(rule_id)
    
    def get_section_rules(self, section: str) -> List[Dict[str, Any]]:
        """Get all rules in a section."""
        rule_ids = self.SECTIONS.get(section, [])
        return [self._parsed_rules.get(rid) for rid in rule_ids if rid in self._parsed_rules]
    
    def build_system_prompt(self, context: Optional[MarketContext] = None) -> str:
        """
        Build dynamic system prompt with optional context injection.
        
        Args:
            context: Optional market context to inject
            
        Returns:
            Complete system prompt string
        """
        parts = [
            "# ICT Market Analyst System",
            "",
            "You are an expert ICT (Inner Circle Trader) analyst maintaining continuous market context.",
            "",
            "## Your Role",
            "- Maintain persistent awareness of market structure evolution",
            "- Track liquidity events and their implications across analyses",
            "- Apply ICT rules consistently",
            "- Remember previous bias states and structure shifts",
            "",
        ]
        
        # Inject current context if available
        if context:
            parts.extend([
                "## Current Market Context (Persistent)",
                "",
                context.to_narrative(),
                "",
            ])
        
        # Dynamic rules injection
        parts.extend([
            "## ICT Framework Rules",
            "",
            "### Market Framework (Rules 1.x)",
            self._format_section_rules("market_framework"),
            "",
            "### Directional Bias (Rules 2.x)",
            self._format_section_rules("directional_bias"),
            "",
            "### Liquidity Concepts (Rules 3.x)",
            self._format_section_rules("liquidity"),
            "",
            "### Price Delivery (Rules 4.x)",
            self._format_section_rules("price_delivery"),
            "",
            "### PD Arrays (Rules 5.x)",
            self._format_section_rules("pd_arrays"),
            "",
            "### Entry Models (Rules 6.x)",
            self._format_section_rules("entry_models"),
            "",
            "### Session Rules (Rules 8.x)",
            self._format_section_rules("session_time"),
            "",
            "### Invalidation Rules (Rules 9.x)",
            self._format_section_rules("invalidation"),
            "",
        ])
        
        # Execution checklist
        parts.extend([
            "## Execution Checklist (Rule 10)",
            "",
            "Before ANY trade decision, verify:",
            "- [ ] HTF bias is clear (Rule 1.1)",
            "- [ ] LTF shows MSS or alignment (Rule 1.2)",
            "- [ ] Price in correct PD zone (Rule 5.1)",
            "- [ ] Liquidity has been swept (Rule 3.4)",
            "- [ ] Session is valid (Rule 8.1)",
            "- [ ] No news cooldown (Rule 8.4)",
            "- [ ] Phase supports entry (DISTRIBUTION or EXPANSION)",
            "- [ ] Risk calculated (Rule 7.1)",
            "",
        ])
        
        # Decision output format
        parts.extend([
            "## Decision Output Format",
            "",
            "You MUST respond with valid JSON in this exact format:",
            "",
            "```json",
            "{",
            '  "decision": "TRADE" | "WAIT" | "NO_TRADE",',
            '  "confidence": 0.0 to 1.0,',
            '  "reasoning": "Detailed analysis citing specific rules",',
            '  "brief_reason": "One sentence summary",',
            '  "rule_citations": ["1.1", "3.4", "6.3"],',
            '  "context_update": "What changed in market state",',
            '  "setup": {',
            '    "direction": "LONG" | "SHORT",',
            '    "entry_price": 1.0850,',
            '    "stop_loss": 1.0820,',
            '    "take_profit": 1.0910,',
            '    "entry_model": "Sweep→Disp→FVG",',
            '    "pd_array_type": "FVG"',
            '  }',
            "}",
            "```",
            "",
            "Note: Only include 'setup' if decision is TRADE.",
            ""
        ])
        
        return "\n".join(parts)
    
    def _format_section_rules(self, section: str) -> str:
        """Format rules from a section as bullet points."""
        rules = self.get_section_rules(section)
        lines = []
        
        for rule in rules:
            if rule:
                what_text = rule.get("what", rule.get("title", ""))[:100]
                lines.append(f"- **{rule['id']} {rule['title']}**: {what_text}")
        
        if not lines:
            # Fallback if rules not parsed
            return self._get_fallback_rules(section)
        
        return "\n".join(lines)
    
    def _get_fallback_rules(self, section: str) -> str:
        """Provide fallback rules if rulebook not loaded."""
        fallbacks = {
            "market_framework": """- **1.1 HTF Bias**: Use 1H for directional bias (HH/HL = Bullish, LH/LL = Bearish)
- **1.2 TF Alignment**: 15M must align with 1H bias
- **1.2.2 Counter-trend**: Prohibited without 1H MSS""",
            
            "directional_bias": """- **2.1 Market Structure**: Track swing highs and lows
- **2.2 BMS**: Break in market structure (continuation)
- **2.3 MSS**: Market structure shift (reversal)
- **2.4 Dealing Range**: Identify accumulation/distribution ranges""",
            
            "liquidity": """- **3.1 Buy/Sell Side**: Identify liquidity pools above/below
- **3.2 Equal H/L**: Equal highs/lows are liquidity targets
- **3.4 Stop Hunt**: Liquidity sweep = potential reversal""",
            
            "price_delivery": """- **4.1 ERC Model**: Expansion → Retracement → Continuation
- **4.2 Power of Three**: Accumulation → Manipulation → Distribution""",
            
            "pd_arrays": """- **5.1 Premium/Discount**: LONG in discount, SHORT in premium
- **5.2 FVG**: Fair value gaps as entry zones
- **5.4 Order Block**: Last candle before displacement""",
            
            "entry_models": """- **6.1 OTE Entry**: MSS + entry at 0.62-0.79 retracement
- **6.3 Sweep→Disp→FVG**: Classic ICT sequence
- **6.5 ICT 2022 Model**: Full confluence entry""",
            
            "session_time": """- **8.1 Kill Zones**: London 02:00-05:00 EST, NY 07:00-10:00 EST
- **8.4 News**: No trades within 30min of high-impact news""",
            
            "invalidation": """- **9.1 Counter-trend**: No counter-trend without 1H MSS
- **9.2 Session**: No trades outside kill zones
- **9.3 Max Trades**: Maximum 2-3 trades per session"""
        }
        return fallbacks.get(section, "No rules defined")
    
    def build_analysis_prompt(
        self,
        observation_summary: str,
        context: Optional[MarketContext] = None
    ) -> str:
        """
        Build the user message prompt for analysis.
        
        This is combined with the system prompt for the LLM.
        """
        parts = [
            "# Market Observation for Analysis",
            "",
            observation_summary,
            "",
            "---",
            "",
            "Analyze this observation using the ICT framework.",
            "Apply the rules and provide your decision in the specified JSON format.",
            "",
        ]
        
        if context:
            parts.extend([
                "Remember: You have analyzed this symbol before.",
                f"This is analysis #{context.analysis_count}.",
                f"Previous decision was: {context.last_decision or 'None'}",
                "",
            ])
        
        parts.append("Provide your analysis and decision now.")
        
        return "\n".join(parts)


# =============================================================================
# Singleton Instance
# =============================================================================

_prompt_builder: Optional[ICTPromptBuilder] = None


def get_prompt_builder() -> ICTPromptBuilder:
    """Get or create the prompt builder singleton."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = ICTPromptBuilder()
    return _prompt_builder
