# Parser Template for New SAST Tools

```python
# parsers/<tool_name>.py
# Copy and customize for each new SAST tool

from __future__ import annotations
from pathlib import Path
from typing import Any
import json

from .base import (
    Finding, ToolConfigBase, run_command, safe_json_parse,
    map_<tool>_severity  # Define in base.py
)


class <ToolName>Parser:
    """Parser for <Tool Name> SAST."""
    
    def build_command(self, target_file: Path, config: ToolConfigBase) -> list[str]:
        """Build command to execute tool on target file."""
        # Get tool-specific config
        tool_config = config.get("<tool_name>", {})
        
        # Build command - use CLI directly for semgrep/pip-audit
        # Use python -m for others
        cmd = ["<tool_cli>", "<args>", str(target_file)]
        
        # Add config if specified
        if tool_config.get("config"):
            cmd.extend(["--config", tool_config["config"]])
            
        return cmd
    
    def parse_output(self, stdout: str, stderr: str, exit_code: int, target_file: Path) -> tuple[list[Finding], str]:
        """Parse tool output into normalized findings."""
        findings = []
        parsed, ok = safe_json_parse(stdout)
        
        if ok and isinstance(parsed, dict):
            # Extract findings from tool-specific JSON structure
            for item in parsed.get("results", []):  # Adjust key per tool
                findings.append({
                    "source": "<ToolName>",
                    "code": item.get("rule_id", ""),
                    "message": item.get("message", ""),
                    "line": item.get("location", {}).get("start_line", 0),
                    "col": item.get("location", {}).get("start_col", 0),
                    "severity": map_<tool>_severity(item.get("severity", "")),
                    "file": str(target_file),
                    "tool_metadata": {
                        "rule_id": item.get("rule_id"),
                        # Add tool-specific metadata
                    }
                })
            status = "SUCCESS"
        elif exit_code != 0 and not stdout.strip():
            # Tool not installed or not in PATH
            status = "NOT_INSTALLED"
        else:
            # Tool ran but output unparseable
            status = "FAILED"
        
        return findings, status
    
    def get_severity(self, finding: Finding) -> str:
        return finding.get("severity", "medium")


parser = <ToolName>Parser()


# =============================================================================
# Add severity mapping to parsers/base.py:
# =============================================================================
# SEVERITY_MAP_<TOOL> = {
#     "CRITICAL": "critical",
#     "HIGH": "high",
#     "MEDIUM": "medium",
#     "LOW": "low",
#     "INFO": "info",
# }
#
# def map_<tool>_severity(severity: str) -> str:
#     return SEVERITY_MAP_<TOOL>.get(severity.upper(), "medium")


# =============================================================================
# Register in parsers/__init__.py:
# =============================================================================
# from .<tool_name> import parser as <tool_name>_parser
#
# PARSERS = {
#     ...
#     "<tool_name>": <tool_name>_parser,
# }
```
