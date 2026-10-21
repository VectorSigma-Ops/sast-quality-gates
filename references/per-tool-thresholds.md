# Per-Tool Threshold Decision Table

## Security vs Quality Separation

| Tool | Category | Critical | High | Medium | Low | Notes |
|------|----------|----------|------|--------|-----|-------|
| bandit | Security | 0 | 0 | 0 | ~150 | LOW findings are info (subprocess import), not vulns |
| semgrep | Security | 0 | 0 | 0 | 0 | ERROR severity = security pattern match |
| pip-audit | Security | 0 | 0 | 0 | 0 | Any CVE = blocking |
| ruff | Quality | 0 | 400 | 800 | 200 | Syntax errors, unused imports, style |
| pyright | Quality | 0 | 300 | 600 | 150 | Type errors, undefined vars |
| radon | Complexity | 0 | 61* | 38* | 100 | CC>10=high, CC>5=medium. Adjust * to current baseline |
| vulture | Dead code | 0 | 100 | 150 | 50 | Optional, often disabled |

## Severity Mapping Rationale

### bandit
- HIGH: Actual vulnerability (eval, exec, hardcoded secrets, SQL injection) → maps to **critical**
- MEDIUM: Potentially unsafe patterns → maps to **high**
- LOW: Info/guidance (importing subprocess, try/except/pass) → maps to **low**
- Rule: `SEVERITY_MAP_BANDIT = {"HIGH": "critical", "MEDIUM": "high", "LOW": "low"}`

### semgrep
- ERROR: Security rule matched → **critical**
- WARNING: Advisory → **high**
- INFO: Style/quality → **medium**

### radon (cyclomatic complexity)
- Never maps to critical — complexity is refactoring guidance, not a security blocker
- CC>10: high (immediate refactoring needed)
- CC>5: medium (refactor guidance)
- CC≤5: low (acceptable)

## Implementation Pattern

```python
# In gate.py
PER_TOOL_THRESHOLDS = {
    "bandit": {"max_findings": 200, "max_critical": 0, "max_high": 0, "max_medium": 0, "max_low": 150},
    "semgrep": {"max_findings": 0, "max_critical": 0, "max_high": 0, "max_medium": 0, "max_low": 0},
    "pip_audit": {"max_findings": 50, "max_critical": 0, "max_high": 0, "max_medium": 0, "max_low": 50},
    "ruff": {"max_findings": 500, "max_critical": 0, "max_high": 400, "max_medium": 800, "max_low": 200},
    "radon": {"max_findings": 500, "max_critical": 0, "max_high": 61, "max_medium": 38, "max_low": 100},
    ...
}

SECURITY_TOOLS = {"bandit", "semgrep", "pip_audit"}

# Evaluate per-tool, then global
for tool_name, tool_thresholds in PER_TOOL_THRESHOLDS.items():
    tool_count = tool_findings.get(tool_name, {})
    for sev, limit in tool_thresholds.items():
        if sev == "max_findings":
            if actual > limit > 0:
                breach = {"security_blocking": tool_name in SECURITY_TOOLS}
```

## Baseline Calibration

When first deploying:
1. Run gate → capture actual finding counts per tool
2. Set `max_*` thresholds to actual + growth margin (e.g., 10-20%)
3. Set security tool thresholds to 0 (zero tolerance)
4. Set `max_findings` to total + 50% margin
5. Re-run to verify gate passes with calibrated thresholds
6. Track baseline in `references/baseline-<version>.md`

## Common Pitfalls

- Setting max_high=0 globally will block on ruff quality findings — use per-tool thresholds
- Bandit LOW→medium mapping makes try/except/pass block the gate — map to `low` instead
- Radon CC>15→critical causes massive failure on legacy codebases — keep critical=0 for radon
- pip-audit deduplication must be class-level (`_seen_vulns`) not instance-level — per-file instances reset the set

- **Security-first thresholds**: `gate-config.yaml` with `max_critical=0, max_high=0` for bandit/semgrep/pip_audit. Zero tolerance for security findings.
- **Cyclomatic complexity threshold**: `max_high=0, max_medium=0` for radon. CC≤5 strict — any function with CC>5 must be refactored before push.
- **pip-audit deduplication**: Add class-level `_seen_vulns: set[str]` in parser to deduplicate by (dependency, vulnerability_id) across all invocations. pip-audit scans ALL installed packages and runs once per file, generating identical results each time.
- **pip-audit runs once per file**: In `audit_dir_async`, pip-audit runs 36 times (once per file) generating identical results each time. Class-level `_seen_vulns` set prevents 36x multiplication of findings.
- **Security tools MUST pass with zero findings**: bandit, semgrep, pip_audit with max_critical=0, max_high=0. Gate fails on ANY security finding.
- **Complexity zero-tolerance**: radon with max_high=0, max_medium=0 blocks any function with CC>5 from pushing to git.