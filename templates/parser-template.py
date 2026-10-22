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

---

## Actual Implementation Pattern (from audit_gate v1.0.0)

### Base Class (parsers/base.py)
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from .finding import Finding, Severity, ToolStatus


class ToolParser(ABC):
    def __init__(self, tool_name: str):
        self.tool_name = tool_name

    @abstractmethod
    def build_command(self, file_path: Path) -> List[str]:
        pass

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> List[Finding]:
        pass

    @abstractmethod
    def get_version_command(self) -> List[str]:
        pass

    def run(self, file_path: Path, timeout: int = 30) -> tuple[ToolStatus, List[Finding], str]:
        cmd = self.build_command(file_path)
        # subprocess.run with timeout, capture stdout/stderr
        # Return (status, findings, error)
```

### Concrete Parser (e.g., parsers/ruff.py)
```python
from .base import ToolParser, safe_json_parse, resolve_tool_path
from ..core.finding import Finding, Severity


class RuffParser(ToolParser):
    def __init__(self):
        super().__init__("ruff")

    def get_version_command(self) -> list[str]:
        return ["ruff", "--version"]

    def build_command(self, file_path: Path) -> list[str]:
        tool_path = resolve_tool_path("ruff")
        return [tool_path, "check", "--output-format=json", "--no-cache", str(file_path)]

    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> list[Finding]:
        data = safe_json_parse(stdout)
        if not data:
            return []
        findings = []
        for item in data:
            findings.append(Finding(
                source="ruff",
                code=item["code"],
                message=item["message"],
                file=str(file_path),
                line=item["location"]["row"],
                col=item["location"]["column"],
                severity=Severity.MEDIUM,  # Map from ruff codes
                tool_metadata={},
            ))
        return findings
```

### Parser Registry (cli.py)
```python
from .parsers import ruff, pyright, bandit, radon, semgrep, pip_audit, vulture

PARSERS = {
    "ruff": ruff.RuffParser(),
    "pyright": pyright.PyrightParser(),
    "bandit": bandit.BanditParser(),
    "radon": radon.RadonParser(),
    "semgrep": semgrep.SemgrepParser(),
    "pip_audit": pip_audit.PipAuditParser(),
    "vulture": vulture.VultureParser(),
}
```

### Key Rules
- **Class naming**: `XxxParser` (e.g., `PipAuditParser` not `Pip_auditParser`)
- **Tool resolution**: Use `resolve_tool_path()` from base.py — checks PATH, then `sys.executable.parent`
- **CLI only for semgrep/pip-audit**: Never use `python -m semgrep` or `python -m pip_audit`
- **safe_json_parse()**: Use for robust JSON extraction from stdout
- **Finding normalization**: All parsers return `Finding` dataclass with source, code, message, file, line, col, severity, tool_metadata
- **Severity mapping**: Map each tool's native severity to `Severity` enum (critical, high, medium, low, info) based on what the severity MEANS for that tool
- **Status codes**: Return `ToolStatus.SUCCESS`, `FAILED`, or `NOT_INSTALLED` from `run()` method
