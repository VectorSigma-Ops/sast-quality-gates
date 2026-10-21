"""Base parser class for SAST tools."""

import json
import subprocess
import shutil
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from ..core.finding import Finding, Severity, ToolStatus
from ..core.thresholds import is_security_tool, SECURITY_TOOLS


class ToolParser(ABC):
    """Base class for SAST tool parsers."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name

    @abstractmethod
    def build_command(self, file_path: Path) -> List[str]:
        """Build command to run tool on a file."""
        pass

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str, file_path: Path) -> List[Finding]:
        """Parse tool output into normalized findings."""
        pass

    def get_version(self) -> str:
        """Get tool version for cache key."""
        try:
            result = subprocess.run(
                self.get_version_command(),
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return "unknown"

    @abstractmethod
    def get_version_command(self) -> List[str]:
        """Command to get tool version."""
        pass

    def run(self, file_path: Path, timeout: int = 30) -> tuple[ToolStatus, List[Finding], str]:
        """Run tool on file and parse findings."""
        cmd = self.build_command(file_path)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=file_path.parent if file_path.parent.exists() else None
            )
            
            if result.returncode == 0 or result.returncode == 1:  # 0=no findings, 1=findings
                findings = self.parse_output(result.stdout, result.stderr, file_path)
                return ToolStatus.SUCCESS, findings, ""
            else:
                return ToolStatus.FAILED, [], f"Exit code {result.returncode}: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return ToolStatus.FAILED, [], f"Timeout after {timeout}s"
        except FileNotFoundError:
            return ToolStatus.NOT_INSTALLED, [], f"{self.tool_name} not found in PATH"
        except Exception as e:
            return ToolStatus.FAILED, [], str(e)


def safe_json_parse(text: str) -> dict | list | None:
    """Safely parse JSON from text, extracting first valid JSON object/array."""
    text = text.strip()
    if not text:
        return None
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object/array in text
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        continue
    return None


def resolve_tool_path(tool: str) -> str:
    """Resolve tool path: checks PATH first, then sys.executable parent for tool binaries."""
    # First check PATH
    path = shutil.which(tool)
    if path:
        return path
    
    # Check Python bin dir (Hermes installs tools alongside Python)
    import sys
    python_bin = Path(sys.executable).parent
    tool_path = python_bin / tool
    if tool_path.exists() and tool_path.is_file():
        return str(tool_path)
    
    return tool  # Fallback to name, let subprocess handle it
