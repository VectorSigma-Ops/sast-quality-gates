"""Parser for pip_audit."""

import json
import re
from pathlib import Path
from typing import List
from .base import ToolParser, safe_json_parse, resolve_tool_path
from ..core.finding import Finding, Severity, ToolStatus


class PipAuditParser(ToolParser):
    """Parser for pip_audit."""

    def __init__(self):
        super().__init__("pip_audit")

    def get_version_command(self) -> list[str]:
        return ['pip-audit', '--version']

    def build_command(self, file_path: Path) -> list[str]:
        tool_path = resolve_tool_path("pip_audit")
        cmd = [tool_path] + [part.format(file=str(file_path)) for part in ['--format', 'json', '--desc', 'on', '--dry-run', '{file}']]
        return cmd

    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> list:
        """Parse pip_audit output into normalized findings."""
        # Implementation specific to pip_audit
        # This is a placeholder - actual parsing depends on tool output format
        return []
