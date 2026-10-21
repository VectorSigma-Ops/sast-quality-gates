---
name: sast-quality-gates
category: software-development
description: Use for multi-tool SAST gates with auto-fix. Hermes hooks.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [sast, quality-gate, auto-fix, security, linting]
    related_skills: [requesting-code-review, test-driven-development, systematic-debugging]
---

# SAST Quality Gates Skill

## When to Use
- Setting up a quality gate that runs multiple SAST tools (ruff, pyright, bandit, radon, semgrep, pip-audit, vulture)
- Building an auto-fix engine that applies fixes from SAST findings with confidence thresholds
- Integrating quality gates with Hermes hooks (pre-commit, pre-push) and middleware
- Configuring telemetry (SDGL, Prometheus, health endpoints) for audit runs

## Procedure: Gate Setup & Execution

### 1. Tool Resolution
- Tools MUST be installed in the Hermes Python environment (`/home/hermes/.hermes/tools/python-*/lib/python*/site-packages/`)
- Use `_resolve_tool_path()` in parsers/base.py: checks PATH first, then `sys.executable.parent` for tool binaries
- `semgrep` and `pip-audit` expose CLI only (`semgrep`, `pip-audit`), not `python -m` modules — parsers must call CLI directly
- Verify all 7 tools with: `for t in ruff pyright bandit radon semgrep pip-audit vulture; do python -m $t --version || $t --version; done`

### 2. Parser Implementation
- Each tool gets a parser in `parsers/<tool>.py` implementing `build_command()` and `parse_output()`
- Return normalized `Finding` dicts: source, code, message, line, col, severity, file, tool_metadata
- Map tool-specific severity to normalized: critical, high, medium, low, info
- Use `safe_json_parse()` for robust JSON extraction from stdout
- Status codes: SUCCESS, FAILED, NOT_INSTALLED

### 3. Gate Configuration
- **Per-tool severity mapping is critical**: normalize each tool's native severity to the global scale based on what the severity MEANS for that tool, not 1:1 mapping. Bandit HIGH = critical (security vuln), semgrep ERROR = critical. Radon HIGH = refactoring guidance only.
- Thresholds (defaults): max_findings=0, max_critical=0, max_high=5, max_medium=20, max_low=100
- **Per-tool threshold overrides**: security tools (bandit, semgrep, pip-audit) should have max_findings=0 or strict limits; quality tools (ruff, pyright) tolerate more findings. Define `PER_TOOL_THRESHOLDS` dict in gate.py and evaluate **per-tool**, then evaluate global totals as a second pass
- `block_on_tool_failure=true` — any tool NOT_INSTALLED or FAILED fails the gate
- Cache: SHA256 file content + config hash + tool versions, TTL default 3600s
- Output formats: json, text, github (annotations), sarif (2.1.0)
- **Security vs quality separation**: NEVER conflate security findings with code quality findings in thresholds. A project with 1000 ruff HIGH findings but 0 bandit findings should PASS a security gate; the reverse should FAIL. Use `SECURITY_TOOLS = {"bandit", "semgrep", "pip_audit"}` set to tag security-blocking breaches

#### 3a. Severity Mapping by Tool
- **bandit**: HIGH→critical (actual vuln), MEDIUM→high, LOW→low (info/guidance like subprocess import)
- **semgrep**: ERROR→critical, WARNING→high, INFO→medium
- **pip-audit**: HIGH/CRITICAL vulns→critical (CVE), MEDIUM→high, LOW→medium
- **radon**: CC>10→high (immediate refactor), CC>5→medium (guidance). Radon NEVER generates critical — complexity is refactoring guidance, not a security blocker
- **ruff/pyright/vulture**: standard critical→critical, error→high, warning→medium, info→low

```python
# Example severity map structure
def map_radon_severity(complexity: int) -> str:
    # Security findings (bandit/semgrep/pip_audit) are the only CRITICAL source.
    # Radon complexity never generates critical - it's refactoring guidance.
    if complexity > 10:
        return "high"
    if complexity > 5:
        return "medium"
    return "low"
```

### 4. Parallel Execution
- Discover Python files, run 7 tools per file in parallel (asyncio/thread pool)
- Aggregate findings across files, evaluate thresholds per-file and global
- Exit codes: 0=PASS, 1=FAIL (threshold breach or tool failure)

### 5. Auto-Fix Engine (hermes-auto-fix)
- FixLoopConfig: max_iterations=250, max_fixes_per_iteration=10, confidence_threshold=0.7
- **Pre-push hooks must not stamp version** — stamping writes to `.project-standards-audit` which modifies files during push, causing git to fail with "files were modified by this hook" even when the hook exits 0. Stamping should only happen via manual `stamp-version` command, never in pre-push.
- Confidence thresholds per fixer: ruff=0.95, vulture=0.9, pip_audit=0.9, bandit=0.85, pyright=0.75, semgrep=0.6, radon=0.3
- Only fixes with confidence ≥ threshold are applied
- **Cyclomatic complexity auto-refactoring**: When radon detects CC>5, attempt structured refactoring using libcst AST transformations. Only apply when confidence ≥ 0.3. Patterns: extract function, simplify conditionals, reduce nesting. Never inline code that would reduce visibility. After each refactoring iteration, verify CC≤5 with re-run of radon.
- Exclude patterns: `**/hooks/*`, `**/patches/*`, `**/tests/**`, `**/scripts/**`
- Fix-verify loop: apply fixes → re-run gate → repeat until PASS or max_iterations
- **Unlimited remediation loop**: `validate-all.py --fix-auto` runs validation → fix → re-validate → repeat until all validators pass or 250-iteration safety cap
- **Test validation after each fix**: After each auto-fix iteration, run `pytest` on the project. If tests fail, abort remediation immediately (fix introduced a regression)
- `--max-iterations` CLI argument: **Removed**. Loop runs until clean (max 250 iterations safety cap). Old `--max-iterations N` is no longer accepted.
- Safety cap of 250 iterations prevents infinite loops while allowing unlimited practical iterations

### 6. Hermes Integration
- `plugin.yaml`: declare hooks and middleware
- `hooks/pre_commit.py`, `hooks/pre_push.py`: run gate on staged files
- `hooks/post_gate_fail.py`: trigger auto-fix on gate failure
- `middleware/telemetry_middleware.py`: emit SDGL events at each phase
- Config via `hermes config set plugins.enabled=true`

### 7. Telemetry & Observability
- SDGL events: audit_dir, file_discovery, audit_file, parallel_execution, cache hit/miss
- Prometheus metrics: findings_total, tool_duration_seconds, gate_result
- Health endpoint: `/health` returns gate status
- Structured JSON logging with run_id correlation

## Pitfalls & Rules

- **Cache key includes tool versions** — upgrade a tool and cache auto-invalidates; do not hardcode versions in key generation
- **Semgrep/pip-audit CLI only** — never use `python -m semgrep` or `python -m pip_audit`; parsers must call `semgrep` and `pip-audit` binaries directly
- **Tool resolution order** — PATH first, then Python bin dir; hermes installs tools alongside Python, not in system PATH
- **Confidence threshold blocks low-confidence fixes** — radon (0.4) and semgrep (0.6) never auto-apply at default 0.8 threshold; this is intentional
- **Vulture false positives** — always verify actual usage before adding `# noqa`; use AST to check if symbol is referenced elsewhere
- **Pyright undefined variable fix** — never inject `var_name = None`; it corrupts code. Return SKIPPED for undefined-variable findings
- **Radon complexity fix** — do not rewrite functions to lower complexity automatically; confidence too low, requires human review
- **Thresholds are per-file AND global** — a single file exceeding max_high=5 fails the gate even if global is under limit
- **block_on_tool_failure=true** — missing tools fail the gate immediately; verify all 7 tools before deploying gate
- **Clean cache before re-test** — `rm -rf ~/.cache/audit_gate` to force fresh runs after tool/config changes
- **semgrep config: auto scans full registry** — use `p/security-audit`, `p/python`, or specific ruleset instead; 428s for 1 finding with `auto` vs ~110s with specific config
- **pip-audit scans entire environment and runs once per file** — it scans ALL installed packages regardless of which file is passed as target. In audit_dir_async, pip-audit runs 36 times (once per file) generating identical results each time. Two fixes needed:
  1. Add class-level `_seen_vulns: set[str]` in parser to deduplicate by (dependency, vulnerability_id) across all invocations
  2. In `core.py audit_dir_async`, deduplicate findings from pip-audit before aggregation
  3. If no requirements.txt exists, run `pip-audit -f json` which scans installed environment — verify with `pip-audit -f json 2>/dev/null` directly first
  4. After deduplicating, pip-audit typically reports 0 findings if dependencies are up to date (run `pip install --upgrade <pkg>` for each vulnerable dep)
- **Thresholds project-specific** — defaults (max_high=5, max_medium=20, max_low=100) may be too strict for real projects; create `gate-config.yaml` with adjusted values based on baseline audit
- **Audit version tracking** — after every gate run, run `audit-gate audit-version .` to check if re-audit is needed; on version bump, new commits, or previous FAIL, use `audit-gate stamp-version . --mode dir` to create `.audit-gate-audit` JSON + git tag `audit-gate-v<version>-<commit>`; persists audit version across re-launches. Note: `audit_gate.cli gate` uses positional `dir` argument, not `--mode dir`. The `audit_gate` module is optional — if not installed, hooks fall back to `scripts.validate-all`. See `references/audit-version-tracking.md` for full details.
- **Unlimited remediation loop**: `validate-all.py --fix-auto` runs until clean with 250-iteration safety cap. No `--max-iterations` flag accepted. Loop runs until all validators pass.
- **Test validation after each fix**: After each auto-fix iteration, run `pytest` on the project. If tests fail, abort remediation immediately (fix introduced a regression). This is enforced by the `_run_project_tests()` helper in `validate-all.py`.
- **Never use `--max-iterations` with `--fix-auto`** — this argument has been removed from `validate-all.py`. Using it will cause: `validate-all.py: error: unrecognized arguments: --max-iterations N`
- **Security-first thresholds**: `gate-config.yaml` with `max_critical=0, max_high=0` for bandit/semgrep/pip_audit. Zero tolerance for security findings.
- **Cyclomatic complexity threshold**: `max_high=0, max_medium=0` for radon. CC≤5 strict — any function with CC>5 must be refactored before push.

- **Auto-remediation CC>5 limitation**: Auto-remediation loop cannot automatically refactor functions with cyclomatic complexity > 5. The loop resolves only "fixable" validators (branch naming, commit message format, release tag generation, git hook installation, simple ruff fixes). CC>5 signifies structural complexity requiring manual review — attempting auto-refactoring at confidence ≥ 0.3 may produce semantically different code. After 250 iterations of safety cap, if CC>5 violations remain, the push is blocked and human refactoring is required. This is intentional: CC>5 guidance is not a security blocker but a code quality mandate.

- **Commit message scope required**: Commit-msg hook enforces conventional commit format `type(scope): subject`. Commit messages without scope (e.g., `chore: remove detect-secrets hook`) fail validation. Always use `chore(project-standards):`, `feat(project-standards):`, etc. The scope identifies the project/area affected, enabling granular gate control and automated remediation of branch/commit/release validators.

- **Pre-commit wrapper script pattern**: When using `language: script` hooks with pre-commit, prefer running target scripts in-place via `python -m module_name` rather than copying to a temp file — `Path(__file__).parent` resolution breaks when the script is moved to a temp directory, causing all sub-validators to report "Script not found". Only copy to temp if pre-commit filesystem restrictions are actually encountered (error: file not found). If copying is necessary, ensure the copied script's working directory is the repo root so SCRIPTS_DIR resolves correctly.
- **Environment variable for skip-tests**: Use `VALIDATE_ALL_SKIP_TESTS=1` environment variable instead of `--skip-tests` CLI flag. pre-commit passes arguments in a way that breaks custom flags. The wrapper script sets this env var before executing `validate-all.py`.
- **PYTHONPATH must include venv site-packages**: Hermes Python installs some packages (e.g., `yaml`, `ruamel.yaml`) in a per-skill venv at `/home/hermes/.hermes/installs/.../venv/lib/python3.14/site-packages`. Hook wrappers must include this path in `PYTHONPATH` alongside the skill root, otherwise validators that import `yaml` will crash with `ModuleNotFoundError`.
- **audit_gate module is optional**: The `audit_gate` SAST package may not be installed. Hook wrappers should check `if python -c "import audit_gate"` and gracefully fall back to `scripts.validate-all` when it is absent. Do not hardcode paths to `audit_gate_skill/src`.
- **Hook receives 0 arguments**: When using `language: script` with `pass_filenames: false`, pre-commit calls the hook with no arguments. The hook must not expect filenames as arguments.
- **Absolute paths required**: Always use absolute paths in hook scripts (`PROJECT_ROOT="/full/path/to/project"`). Relative paths fail in pre-commit context.
- **pre-commit clean + re-install**: After modifying hook config, run `pre-commit clean` and `pre-commit install --hook-type pre-push` to refresh the hook installation.
- **Test validation after each fix**: After each auto-fix iteration in the remediation loop, run `pytest` on the project. If tests fail, abort remediation immediately (fix introduced a regression). This is enforced by `_run_project_tests()` helper in `validate-all.py`.
- **pip-audit deduplication**: Add class-level `_seen_vulns: set[str]` in parser to deduplicate by (dependency, vulnerability_id) across all invocations. pip-audit scans ALL installed packages and runs once per file, generating identical results each time.
- **Security-first thresholds**: `gate-config.yaml` with `max_critical=0, max_high=0` for bandit/semgrep/pip_audit. Zero tolerance for security findings.
- **Cyclomatic complexity threshold**: `max_high=0, max_medium=0` for radon. CC≤5 strict — any function with CC>5 must be refactored before push.

## References
- `references/gate-config.md` — threshold decision table, config schema
- `references/per-tool-thresholds.md` — per-tool threshold decision table, severity mapping rationale, baseline calibration, common pitfalls
- `references/tool-versions.md` — tested tool versions, CLI vs module matrix, pre-commit wrapper pattern
- `references/hermes-integration.md` — plugin.yaml, hooks, middleware patterns, pre-push auto-remediation flow
- `references/confidence-thresholds.md` — per-fixer confidence rationale, tuning guide
- `references/audit-version-tracking.md` — version tracking and stamping after SAST gates; CLI commands `audit-version`, `stamp-version`, `check-remote`; `.audit-gate-audit` record format; git tag creation `audit-gate-v<version>-<sha>`; re-validation decision logic; project-standards integration matrix
- `references/auto-remediation-loop.md` — unlimited remediation loop, pre-push hook flow, wrapper script pattern, test validation, safety cap

## Templates
- `templates/gate-config.yaml` — starter gate configuration
- `templates/plugin.yaml` — Hermes plugin declaration
- `templates/parser-template.py` — boilerplate for new tool parsers

## Scripts
- `scripts/verify_tools.py` — verify all 7 SAST tools are installed and functional
- `scripts/clear_cache.py` — clear audit gate cache
