# Hermes Integration Patterns

## Plugin Declaration (plugin.yaml)

```yaml
name: sast-quality-gate
version: 3.0.0
description: Multi-tool SAST quality gate with auto-fix
hooks:
  pre_commit: sast_quality_gate.hooks:pre_commit_hook
  pre_push: sast_quality_gate.hooks:pre_push_hook
  post_gate_fail: sast_quality_gate.hooks:post_gate_fail_hook
middleware:
  - sast_quality_gate.middleware:telemetry_middleware
config_schema:
  thresholds:
    type: object
    properties:
      max_findings: {type: integer, default: 0}
      max_critical: {type: integer, default: 0}
      max_high: {type: integer, default: 5}
      max_medium: {type: integer, default: 20}
      max_low: {type: integer, default: 100}
  block_on_tool_failure: {type: boolean, default: true}
  cache:
    type: object
    properties:
      enabled: {type: boolean, default: true}
      ttl_seconds: {type: integer, default: 3600}
```

## Hook Implementations

### pre_commit_hook
```python
async def pre_commit_hook(ctx):
    staged_files = get_staged_python_files()
    if not staged_files:
        return
    result = await run_gate(staged_files, mode="file")
    if result.exit_code != 0:
        raise GateFailedError(result)
```

### Direct Git Hooks Pattern (Recommended)

**Abandon pre-commit framework for Hermes hooks** — it uses system Python (3.13) without project-standards installed. Use direct `.git/hooks/*` scripts calling Hermes Python (3.14.7) with exported PYTHONPATH.

```bash
# .git/hooks/pre-commit
#!/bin/bash
INSTALL_PYTHON=$(find /home/hermes/.hermes/tools -maxdepth 4 -name "python3*" -type f -executable 2>/dev/null | grep -E "python3\.[0-9]+" | head -1)
if [ -z "$INSTALL_PYTHON" ]; then
    INSTALL_PYTHON="/usr/bin/python3"
fi
export PYTHONPATH="/home/hermes/.hermes/skills/infrastructure/project-standards-skill-project-standards:${PYTHONPATH}"
exec "$INSTALL_PYTHON" -m audit_gate.cli gate . --format text
```

```bash
# .git/hooks/commit-msg
#!/bin/bash
INSTALL_PYTHON=$(find /home/hermes/.hermes/tools -maxdepth 4 -name "python3*" -type f -executable 2>/dev/null | grep -E "python3\.[0-9]+" | head -1)
if [ -z "$INSTALL_PYTHON" ]; then
    INSTALL_PYTHON="/usr/bin/python3"
fi
export PYTHONPATH="/home/hermes/.hermes/skills/infrastructure/project-standards-skill-project-standards:${PYTHONPATH}"
COMMIT_MSG_FILE="$1"
exec "$INSTALL_PYTHON" -m audit_gate.cli validate-commit "$COMMIT_MSG_FILE" --fix
```

```bash
# .git/hooks/pre-push
#!/bin/bash
INSTALL_PYTHON=$(find /home/hermes/.hermes/tools -maxdepth 4 -name "python3*" -type f -executable 2>/dev/null | grep -E "python3\.[0-9]+" | head -1)
if [ -z "$INSTALL_PYTHON" ]; then
    INSTALL_PYTHON="/usr/bin/python3"
fi
export PYTHONPATH="/home/hermes/.hermes/skills/infrastructure/project-standards-skill-project-standards:${PYTHONPATH}"

# Read stdin for push refs
while read local_ref local_sha remote_ref remote_sha; do
    if echo "$local_ref" | grep -q "^refs/tags/"; then
        TAG_NAME=$(echo "$local_ref" | sed 's|refs/tags/||')
        "$INSTALL_PYTHON" -m audit_gate.cli validate-release "$TAG_NAME" || exit 1
    elif echo "$local_ref" | grep -q "^refs/heads/"; then
        BRANCH_NAME=$(echo "$local_ref" | sed 's|refs/heads/||')
        "$INSTALL_PYTHON" -m audit_gate.cli gate . --tools "bandit,semgrep,pip_audit" --format text || exit 1
    fi
done

exec "$INSTALL_PYTHON" -m audit_gate.cli gate . --format text
```

**Key differences from pre-commit framework**:
- No framework intermediary — hooks call Hermes Python directly
- Dynamic Python detection avoids hardcoded paths with glob `****` issues
- PYTHONPATH export ensures skill modules and dependencies are importable
- Module invocation: `python -m audit_gate.cli` not `python -m audit_gate`
- Security-first on branch pushes (bandit, semgrep, pip_audit only), full gate on final validation
- Commit-msg hook receives commit message file as `$1`

### pre_push_hook (with auto-remediation)
The pre-push hook with auto-remediation uses a bash wrapper script for full-project audit + auto-fix:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: audit-gate-pre-push
      name: audit-gate (Pre-push - full project audit + auto-fix)
      entry: .pre-commit-hooks/audit-gate-pre-push-auto
      language: script
      types: [python]
      stages: [pre-push]
      pass_filenames: false
      verbose: true
      always_run: true
```

```bash
# .pre-commit-hooks/audit-gate-pre-push-auto
#!/bin/bash
set -euo pipefail

PYTHON="$(ls -1 /home/hermes/.hermes/tools/python-3.14.7+*/bin/python 2>/dev/null | head -1)"
export PYTHONPATH="/path/to/project:/path/to/venv/lib/python3.14/site-packages:${PYTHONPATH:-}"
PROJECT_ROOT="/path/to/project"

# Step 0: Optional SAST gate (audit_gate) — only if the module is installed
if $PYTHON -c "import audit_gate" 2>/dev/null; then
    echo "Step 0: Running SAST quality gate..."
    if $PYTHON -m audit_gate.cli gate dir --format text; then
        echo "SAST gate passed - no findings"
    else
        echo "SAST gate failed - initiating auto-remediation..."
        export VALIDATE_ALL_SKIP_TESTS=1
        "$PROJECT_ROOT/.pre-commit-hooks/validate-all-skip-tests" --fix-auto --format text --target-path "$PROJECT_ROOT" || exit 1
        if $PYTHON -m audit_gate.cli gate dir --format text; then
            echo "SAST verification passed"
        else
            echo "SAST gate still shows findings after remediation"
            exit 1
        fi
    fi
else
    echo "Step 0: audit_gate module not installed — skipping SAST gate"
fi

# Step 1: Run project-standards validation with auto-remediation
echo "Step 1: Running project-standards validation with auto-fix..."
echo "    This will iterate: validate -> fix -> re-validate until clean"
echo "    Safety cap: 250 iterations"
echo "    Note: Tests are skipped in pre-push hook; run 'validate-all.py --fix-auto' manually for full validation"

if "$PROJECT_ROOT/.pre-commit-hooks/validate-all-skip-tests" --fix-auto --format text --target-path "$PROJECT_ROOT"; then
    echo "Auto-remediation completed successfully"
else
    exit 1
fi

echo "=========================================="
echo "ALL CHECKS PASSED - PUSH ALLOWED"
echo "=========================================="
exit 0
```

```bash
# .pre-commit-hooks/validate-all-skip-tests
#!/bin/bash
export VALIDATE_ALL_SKIP_TESTS=1
export PYTHONPATH="/path/to/project:/path/to/venv/lib/python3.14/site-packages:${PYTHONPATH:-}"
PYTHON="$(ls -1 /home/hermes/.hermes/tools/python-3.14.7+*/bin/python 2>/dev/null | head -1)"
exec "$PYTHON" -m scripts.validate-all "$@"
```

**Key Implementation Details**:
- Tests skipped in hook (`VALIDATE_ALL_SKIP_TESTS=1`); manual `validate-all.py --fix-auto` runs tests after each fix
- Safety cap: 250 iterations (`MAX_ITERATIONS_SAFETY = 250` in `validate-all.py`)
- `--max-iterations` flag has been removed
- Hook receives 0 arguments (`pass_filenames: false`, `language: script`)
- Wrapper runs `scripts.validate-all` in-place via `-m` (NOT temp copy) to preserve `Path(__file__).parent` resolution
- PYTHONPATH must include both skill root and venv site-packages (for yaml, etc.)
- Do NOT stamp version in pre-push — stamping modifies `.project-standards-audit` which blocks git push
- Absolute paths required: `PROJECT_ROOT` defined at script top
- `pre-commit clean` + re-install needed after hook config changes

### post_gate_fail_hook
```python
async def post_gate_fail_hook(ctx):
    # Trigger auto-fix on gate failure
    from hermes_auto_fix import auto_fix
    fix_result = await auto_fix(ctx.target_files)
    if fix_result.fixes_applied > 0:
        # Re-run gate to verify
        verify_result = await run_gate(ctx.target_files)
        if verify_result.exit_code == 0:
            # Auto-commit fixes if configured
            await commit_fixes()
```

## Middleware: Telemetry

```python
async def telemetry_middleware(ctx, next):
    run_id = uuid4()
    emit_sdgl("audit_gate_event", phase="start", run_id=run_id)
    try:
        result = await next(ctx)
        emit_sdgl("audit_gate_event", phase="complete", run_id=run_id, result=result)
        return result
    except Exception as e:
        emit_sdgl("audit_gate_event", phase="error", run_id=run_id, error=str(e))
        raise
```

## SDGL Event Phases

- `audit_dir` — directory scan started
- `file_discovery` — Python files found
- `audit_file` — per-file audit start
- `parallel_execution` — 7 tools launched
- `cache` — hit/miss
- `audit_file` — per-file complete with findings count
- `audit_dir` — complete with totals

## Enabling in Hermes

```bash
hermes config set plugins.enabled=true
hermes config set skills.sast-quality-gate.enabled=true
```
