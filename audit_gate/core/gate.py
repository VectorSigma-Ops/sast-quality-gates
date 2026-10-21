"""Gate evaluation logic for SAST quality gates."""

import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field
from .finding import Finding, Severity, ToolStatus
from .thresholds import (
    DEFAULT_THRESHOLDS, DEFAULT_GLOBAL, get_tool_thresholds,
    is_security_tool, SECURITY_TOOLS
)


@dataclass
class ToolResult:
    """Result of a single tool execution."""
    tool: str
    status: ToolStatus
    findings: List[Finding] = field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class GateReport:
    """Complete gate evaluation report."""
    results: List[ToolResult]
    passed: bool
    total_findings: int
    by_tool: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


class GateEvaluator:
    """Evaluates SAST findings against thresholds."""

    def __init__(
        self,
        tool_thresholds: dict = None,
        global_thresholds = None,
        cache_ttl: int = 3600,
        cache_dir: Path = None
    ):
        self.tool_thresholds = tool_thresholds or {}
        self.global_thresholds = DEFAULT_GLOBAL
        self.cache_ttl = cache_ttl
        self.cache_dir = cache_dir or Path.home() / ".cache" / "audit_gate"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._seen_vulns: Set[str] = set()  # For pip-audit deduplication

    def evaluate_tool(self, tool: str, findings: List[Finding]) -> Tuple[bool, List[str]]:
        """Evaluate findings for a single tool against its thresholds.
        Returns (passed, list of violation messages)."""
        violations = []
        thresholds = self.tool_thresholds.get(tool, DEFAULT_THRESHOLDS.get(tool))
        if not thresholds:
            return True, []

        # Count by severity
        counts = {s.value: 0 for s in Severity}
        for f in findings:
            counts[f.severity.value] += 1

        # Check per-severity thresholds
        if counts.get("critical", 0) > 0 and thresholds.max_critical == 0:
            violations.append(f"{tool}: {counts['critical']} critical findings (max: 0)")
        elif counts.get("critical", 0) > thresholds.max_critical:
            violations.append(f"{tool}: {counts['critical']} critical (max: {thresholds.max_critical})")

        if counts.get("high", 0) > 0 and thresholds.max_high == 0:
            violations.append(f"{tool}: {counts['high']} high findings (max: 0)")
        elif counts.get("high", 0) > thresholds.max_high:
            violations.append(f"{tool}: {counts['high']} high (max: {thresholds.max_high})")

        if counts.get("medium", 0) > thresholds.max_medium:
            violations.append(f"{tool}: {counts['medium']} medium (max: {thresholds.max_medium})")

        if counts.get("low", 0) > thresholds.max_low:
            violations.append(f"{tool}: {counts['low']} low (max: {thresholds.max_low})")

        total = sum(counts.values())
        if total > thresholds.max_findings:
            violations.append(f"{tool}: {total} total findings (max: {thresholds.max_findings})")

        return len(violations) == 0, violations

    def evaluate_global(self, all_findings: List[Finding], global_thresholds = None) -> Tuple[bool, List[str]]:
        """Evaluate all findings against global thresholds."""
        global_thresholds = global_thresholds or DEFAULT_GLOBAL
        violations = []

        counts = {s.value: 0 for s in Severity}
        for f in all_findings:
            counts[f.severity.value] += 1

        if counts.get("critical", 0) > global_thresholds.max_critical:
            violations.append(f"Global: {counts['critical']} critical (max: {global_thresholds.max_critical})")
        if counts.get("high", 0) > global_thresholds.max_high:
            violations.append(f"Global: {counts['high']} high (max: {global_thresholds.max_high})")
        if counts.get("medium", 0) > global_thresholds.max_medium:
            violations.append(f"Global: {counts['medium']} medium (max: {global_thresholds.max_medium})")
        if counts.get("low", 0) > global_thresholds.max_low:
            violations.append(f"Global: {counts['low']} low (max: {global_thresholds.max_low})")

        total = sum(counts.values())
        if total > global_thresholds.max_total:
            violations.append(f"Global: {total} total findings (max: {global_thresholds.max_total})")

        return len(violations) == 0, violations

    def evaluate(self, results: List[ToolResult]) -> GateReport:
        """Evaluate all tool results."""
        all_findings = []
        by_tool = {}
        by_severity = {s.value: 0 for s in Severity}
        all_violations = []

        for result in results:
            tool = result.tool
            passed, violations = self.evaluate_tool(tool, result.findings)
            if not passed:
                all_violations.extend(violations)
            
            tool_count = len(result.findings)
            by_tool[tool] = tool_count
            all_findings.extend(result.findings)

            for f in result.findings:
                self._seen_vulns.add(f"{f.file}:{f.line}:{f.code}")

            for f in result.findings:
                by_severity[f.severity.value] += 1

        # Global evaluation
        global_passed, global_violations = self.evaluate_global(all_findings)
        all_violations.extend(global_violations)

        total_findings = sum(by_tool.values())
        passed = len(all_violations) == 0

        return GateReport(
            results=results,
            passed=passed,
            total_findings=total_findings,
            by_tool=by_tool,
            by_severity=by_severity,
            duration_ms=0.0,  # Set by caller
        )

    def _get_cache_key(self, file_path: Path, tool: str, tool_version: str) -> str:
        """Generate cache key for file+tool+version."""
        content = file_path.read_bytes() if file_path.exists() else b""
        key_data = f"{tool}:{tool_version}:{hashlib.sha256(content).hexdigest()}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get_cached_findings(self, file_path: Path, tool: str, tool_version: str) -> List[Finding] | None:
        """Get cached findings if valid."""
        key = self._get_cache_key(file_path, tool, tool_version)
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            if time.time() - data["timestamp"] > self.cache_ttl:
                return None
            return [Finding.from_dict(f) for f in data["findings"]]
        except Exception:
            return None

    def cache_findings(self, file_path: Path, tool: str, tool_version: str, findings: List[Finding]):
        """Cache findings for file+tool."""
        key = self._get_cache_key(file_path, tool, tool_version)
        cache_file = self.cache_dir / f"{key}.json"
        try:
            data = {
                "timestamp": time.time(),
                "tool": tool,
                "tool_version": tool_version,
                "findings": [f.to_dict() for f in findings],
            }
            with open(cache_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
