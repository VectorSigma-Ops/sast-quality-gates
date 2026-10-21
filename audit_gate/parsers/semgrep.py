"""Parser for semgrep."""

import json
import re
from pathlib import Path
from typing import List
from .base import ToolParser, safe_json_parse, resolve_tool_path
from ..core.finding import Finding, Severity, ToolStatus


class SemgrepParser(ToolParser):
    """Parser for semgrep."""

    def __init__(self):
        super().__init__("semgrep")

    def get_version_command(self) -> list[str]:
        return ['semgrep', '--version']

    def build_command(self, file_path: Path) -> list[str]:
        tool_path = resolve_tool_path("semgrep")
        cmd = [tool_path] + [part.format(file=str(file_path)) for part in ['--config=auto', '--json', '{file}']]
        return cmd

    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> list:
        """Parse semgrep output into normalized findings."""
        # Implementation specific to semgrep
        # This is a placeholder - actual parsing depends on tool output format
        return []
