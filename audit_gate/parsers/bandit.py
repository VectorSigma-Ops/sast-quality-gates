"""Parser for bandit."""

import json
import re
from pathlib import Path
from typing import List
from .base import ToolParser, safe_json_parse, resolve_tool_path
from ..core.finding import Finding, Severity, ToolStatus


class BanditParser(ToolParser):
    """Parser for bandit."""

    def __init__(self):
        super().__init__("bandit")

    def get_version_command(self) -> list[str]:
        return ['bandit', '--version']

    def build_command(self, file_path: Path) -> list[str]:
        tool_path = resolve_tool_path("bandit")
        cmd = [tool_path] + [part.format(file=str(file_path)) for part in ['-f', 'json', '-r', '{file}']]
        return cmd

    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> list:
        """Parse bandit output into normalized findings."""
        # Implementation specific to bandit
        # This is a placeholder - actual parsing depends on tool output format
        return []
