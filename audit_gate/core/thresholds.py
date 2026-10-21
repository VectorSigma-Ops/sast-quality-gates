"""Threshold configuration for quality gates."""

from dataclasses import dataclass, field
from typing import Dict, Optional
from .finding import Severity


# Tool classification
SECURITY_TOOLS = {"bandit", "semgrep", "pip_audit"}
QUALITY_TOOLS = {"ruff", "pyright", "radon", "vulture"}
ALL_TOOLS = SECURITY_TOOLS | QUALITY_TOOLS


@dataclass
class ToolThresholds:
    """Per-tool threshold overrides."""
    max_critical: int = 0
    max_high: int = 0
    max_medium: int = 0
    max_low: int = 100
    max_findings: int = 100  # Total findings per tool


# Default thresholds - security tools are strict, quality tools more lenient
DEFAULT_THRESHOLDS: dict[str, ToolThresholds] = {
    # Security tools - zero tolerance
    "bandit": ToolThresholds(max_critical=0, max_high=0, max_medium=5, max_low=20, max_findings=50),
    "semgrep": ToolThresholds(max_critical=0, max_high=0, max_medium=5, max_low=20, max_findings=50),
    "pip_audit": ToolThresholds(max_critical=0, max_high=0, max_medium=5, max_low=20, max_findings=50),
    
    # Quality tools - more lenient
    "ruff": ToolThresholds(max_critical=0, max_high=5, max_medium=20, max_low=100, max_findings=200),
    "pyright": ToolThresholds(max_critical=0, max_high=5, max_medium=20, max_low=100, max_findings=200),
    "radon": ToolThresholds(max_critical=0, max_high=0, max_medium=0, max_low=100, max_findings=50),  # CC<=5 strict
    "vulture": ToolThresholds(max_critical=0, max_high=5, max_medium=20, max_low=100, max_findings=100),
}


# Global thresholds (second pass after per-tool)
@dataclass
class GlobalThresholds:
    max_critical: int = 0
    max_high: int = 0
    max_medium: int = 20
    max_low: int = 100
    max_total: int = 200


DEFAULT_GLOBAL = GlobalThresholds()


def get_tool_thresholds(tool: str) -> ToolThresholds:
    """Get thresholds for a specific tool."""
    return DEFAULT_THRESHOLDS.get(tool, ToolThresholds())


def is_security_tool(tool: str) -> bool:
    """Check if tool is a security tool."""
    return tool in SECURITY_TOOLS
