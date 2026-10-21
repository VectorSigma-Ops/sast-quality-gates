"""Finding dataclass for normalized SAST findings."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class Severity(str, Enum):
    """Normalized severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ToolStatus(str, Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_INSTALLED = "not_installed"


@dataclass
class Finding:
    """Normalized finding from a SAST tool."""
    source: str                    # Tool name (ruff, bandit, etc.)
    code: str                      # Rule/finding code
    message: str                   # Human-readable message
    file: str                      # File path
    line: int                      # Line number (1-indexed)
    col: int = 0                   # Column number (0-indexed)
    severity: Severity = Severity.MEDIUM
    tool_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "severity": self.severity.value,
            "tool_metadata": self.tool_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Finding":
        return cls(
            source=data["source"],
            code=data["code"],
            message=data["message"],
            file=data["file"],
            line=data["line"],
            col=data.get("col", 0),
            severity=Severity(data.get("severity", "medium")),
            tool_metadata=data.get("tool_metadata", {}),
        )
