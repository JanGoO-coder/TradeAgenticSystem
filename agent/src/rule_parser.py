"""
Rule Body Parser for ICT Rulebook.

Parses the markdown rulebook into structured objects for use by the agent.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class Rule(BaseModel):
    """Represents a single rule from the rulebook."""
    id: str  # e.g., "1.1", "6.1"
    title: str
    content: str  # Full markdown content
    sections: Dict[str, str]  # What, Why, When valid, When invalid

class RuleParser:
    """Parses markdown rulebook into structured rules."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.rules: Dict[str, Rule] = {}
        self._parse()

    def _parse(self):
        """Parse file content into rules."""
        if not self.file_path.exists():
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by headers
        # Regex to find rule headers like "### 1.1 Higher Timeframe Bias"
        # We assume rules start with header level 2 or 3 and a number
        lines = content.split('\n')
        
        current_rule_id = None
        current_rule_title = None
        current_lines = []
        
        rule_header_pattern = re.compile(r'^(#{2,4})\s+(\d+(\.\d+)*)\s+(.+)$')
        
        for line in lines:
            match = rule_header_pattern.match(line)
            if match:
                # Save previous rule if exists
                if current_rule_id:
                    self._process_rule_chunk(current_rule_id, current_rule_title, current_lines)
                
                # Start new rule
                current_rule_id = match.group(2)
                current_rule_title = match.group(4).strip()
                current_lines = []
            else:
                current_lines.append(line)
        
        # Save last rule
        if current_rule_id:
            self._process_rule_chunk(current_rule_id, current_rule_title, current_lines)

    def _process_rule_chunk(self, rule_id: str, title: str, lines: List[str]):
        """Process a chunk of lines for a single rule."""
        full_content = "\n".join(lines).strip()
        
        # Extract sections (What, Why, When valid, etc.)
        sections = {}
        current_section = None
        section_buffer = []

        # Common section keys in the rulebook
        section_keys = ["What:", "Why:", "When valid:", "When invalid:", "When:", "When not:"]
        
        for line in lines:
            stripped = line.strip()
            
            # Check if line starts with a section key
            found_key = False
            for key in section_keys:
                if stripped.startswith(key) or stripped.startswith(f"**{key}"):
                    # Save previous section
                    if current_section:
                        sections[current_section] = "\n".join(section_buffer).strip()
                    
                    # Start new section
                    # Remove the key and any bold formatting from the key
                    clean_key = key.replace(":", "").replace("*", "")
                    current_section = clean_key
                    
                    # Content might be on the same line
                    # Handle "**What:** Content" or "What: Content"
                    content_start = line.find(key) + len(key)
                    # If it was bolded like **What:**, we need to account for trailing **
                    if "**" in line[content_start:]:
                         content_start = line.find("**", content_start) + 2
                    
                    remainder = line[content_start:].strip()
                    section_buffer = [remainder] if remainder else []
                    found_key = True
                    break
            
            if not found_key:
                if current_section:
                    section_buffer.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = "\n".join(section_buffer).strip()

        self.rules[rule_id] = Rule(
            id=rule_id,
            title=title,
            content=full_content,
            sections=sections
        )

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a specific rule by ID."""
        return self.rules.get(rule_id)

    def get_rules_by_keyword(self, keyword: str) -> List[Rule]:
        """Search rules by keyword in title or content."""
        results = []
        term = keyword.lower()
        for rule in self.rules.values():
            if term in rule.title.lower() or term in rule.content.lower():
                results.append(rule)
        return results

    def get_related_rules(self, trigger_rule_id: str) -> List[Rule]:
        """
        Get rules related to the trigger rule.
        Uses the hierarchy (e.g., 1.1 implies checking 1.1.x).
        """
        related = []
        base_id = trigger_rule_id.split('.')[0]
        
        for rid, rule in self.rules.items():
            if rid.startswith(trigger_rule_id) and rid != trigger_rule_id:
                related.append(rule)
        
        return related

# Singleton access
_parser = None

def get_rule_parser(path: Path = Path("rules/rules/ICT_Rulebook_V1.md")) -> RuleParser:
    global _parser
    if _parser is None:
        # Handle relative path from agent root
        repo_root = Path(__file__).parent.parent.parent
        full_path = repo_root / path
        _parser = RuleParser(full_path)
    return _parser
