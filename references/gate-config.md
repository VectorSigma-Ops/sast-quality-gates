# Gate Configuration Reference

## Default Thresholds

| Threshold | Default | Purpose |
|-----------|---------|---------|
| max_findings | 0 | Global total findings limit |
| max_critical | 0 | Zero tolerance for critical |
| max_high | 5 | Max high-severity per file & global |
| max_medium | 20 | Max medium-severity per file & global |
| max_low | 100 | Max low-severity per file & global |
| block_on_tool_failure | true | Fail gate if any tool fails |

## Per-Tool Thresholds (Security-First)

Security tools (bandit, semgrep, pip-audit) **ALWAYS** use zero tolerance for CRITICAL/HIGH/MEDIUM regardless of global config:

| Tool | Category | max_critical | max_high | max_medium | max_low |
|------|----------|-------------|----------|------------|---------|
| bandit | Security | 0 | 0 | 0 | 150 |
| semgrep | Security | 0 | 0 | 0 | 0 |
| pip-audit | Security | 0 | 0 | 0 | 0 |
| ruff | Quality | 0 | 400 | 800 | 200 |
| pyright | Quality | 0 | 300 | 600 | 150 |
| radon | Complexity | 0 | 61* | 38* | 100 |
| vulture | Dead code | 0 | 100 | 150 | 50 |

* radon thresholds are baseline-dependent — set max_high to current CC>10 count, max_medium to current CC>5 count. See `references/per-tool-thresholds.md` for calibration.

**Severity mapping must be per-tool**:
- bandit HIGH → "critical" (actual security vuln like eval/exec), MEDIUM → "high", LOW → "low" (subprocess import, try/except/pass are guidance, not vulnerabilities)
- semgrep ERROR → "critical" (security pattern matched), WARNING → "high", INFO → "medium"
- radon: CC>10→"high", CC>5→"medium". Radon NEVER generates critical.

Implementation in `gate.py`: `PER_TOOL_THRESHOLDS` dict + `SECURITY_TOOLS = {"bandit", "semgrep", "pip_audit"}` set. Evaluate per-tool first (with tagged `security_blocking` breaches), then global totals as a second pass. Gate FAILs if ANY per-tool threshold is exceeded.

## Threshold Evaluation
- **Per-file**: Each file evaluated independently against thresholds
- **Global**: Aggregated across all files
- **Per-tool**: Security tools (bandit, semgrep, pip-audit) always zero tolerance; code quality tools have separate limits
- Gate FAILs if ANY per-file OR global OR per-tool threshold exceeded

## Config Schema (YAML)

```yaml
thresholds:
  max_findings: 0
  max_critical: 0
  max_high: 5
  max_medium: 20
  max_low: 100
block_on_tool_failure: true
cache:
  enabled: true
  ttl_seconds: 3600
  path: "~/.cache/audit_gate"
tools:
  ruff:
    enabled: true
    config: "pyproject.toml"
  pyright:
    enabled: true
    config: "pyproject.toml"
  bandit:
    enabled: true
    config: ".bandit"
  radon:
    enabled: true
    cc_threshold: 5  # Max cyclomatic complexity
  semgrep:
    enabled: true
    config: "p/security-audit"  # NOT 'auto' — scans full registry (428s vs 110s)
  pip_audit:
    enabled: true
  vulture:
    enabled: false  # Often NOT_INSTALLED at runtime; set enabled=false to prevent failures
```

## Threshold Tuning Guide

- **Strict** (CI/CD): max_high=0, max_medium=5, max_low=20
- **Balanced** (default): max_high=5, max_medium=20, max_low=100
- **Lenient** (legacy): max_high=20, max_medium=50, max_low=200
- **Disable**: set to -1 to ignore that severity

## Environment Overrides

All thresholds can be overridden via CLI: `--max-high 10 --max-medium 30`

## Common Pitfalls

- **vulture NOT_INSTALLED**: Despite `pip install` showing it, vulture may fail at runtime. Set `enabled: false` in config rather than relying on tool resolution.
- **semgrep config**: Using `auto` scans the full Semgrep registry (428s for 1 finding). Use `p/security-audit` or specific ruleset (~110s).
- **pip-audit scope**: Default scans entire environment (175s). Use `--requirement requirements.txt` to limit scope (121s).
- **Cache stale**: After tool/config changes, `rm -rf ~/.cache/audit_gate` to force fresh runs.