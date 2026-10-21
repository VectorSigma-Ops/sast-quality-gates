### 5. Auto-Fix Engine (hermes-auto-fix)
- FixLoopConfig: max_iterations=2, max_fixes_per_iteration=10, confidence_threshold=0.8
- Confidence thresholds per fixer: ruff=0.95, vulture=0.9, pip_audit=0.9, bandit=0.85, pyright=0.75, semgrep=0.6, radon=0.4
- Only fixes with confidence ≥ threshold are applied
- Exclude patterns: `**/hooks/*`, `**/patches/*`, `**/tests/**`, `**/scripts/**`
- Fix-verify loop: apply fixes → re-run gate → repeat until PASS or max_iterations
- **Unlimited remediation loop**: `validate-all.py --fix-auto` runs validation → fix → re-validate → repeat until all validators pass or 250-iteration safety cap
- **Test validation after each fix**: After each auto-fix iteration, run `pytest` on the project. If tests fail, abort remediation immediately (fix introduced a regression). This is enforced by the `_run_project_tests()` helper in `validate-all.py`.

- **Baseline pre-existing failure tracking**: The `_run_project_tests()` function establishes a baseline of known test failures at the start of the remediation loop. On each iteration, it checks if any newly introduced failures exist — pre-existing failures are tolerated (the loop continues), but any new failures caused by the remediation abort the loop immediately. This prevents the safety cap from being wasted on projects with inherently broken test suites.
- `--max-iterations` CLI argument: **Removed**. Loop runs until clean (max 250 iterations safety cap). Old `--max-iterations N` is no longer accepted.
- Safety cap of 250 iterations prevents infinite loops while allowing unlimited practical iterations

### 5a. Pre-Push Hook Auto-Remediation Flow
The pre-push hook implements full-project auto-remediation on every `git push`:

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

**Flow**:
1. Step 0: If `audit_gate` module is installed, run SAST gate (`audit_gate.cli gate dir`); if not installed, skip
2. Step 1: Run `validate-all-skip-tests --fix-auto --target-path $PROJECT_ROOT` (auto-remediation loop)
3. On remediation success → allow push (NO stamping — stamping modifies files and blocks push)
4. On remediation failure (250 iterations cap) → block push

**Key Implementation Details**:
- Tests skipped in hook (`VALIDATE_ALL_SKIP_TESTS=1`); manual `validate-all.py --fix-auto` runs tests after each fix
- Safety cap: 250 iterations (`MAX_ITERATIONS_SAFETY = 250` in `validate-all.py`)
- `--max-iterations` flag has been removed
- Hook receives 0 arguments (`pass_filenames: false`, `language: script`)
- Wrapper runs `scripts.validate-all` in-place via `-m` (NOT temp copy) to preserve `Path(__file__).parent` resolution
- PYTHONPATH must include both skill root and venv site-packages (for yaml, etc.)
- Do NOT stamp version in pre-push — stamping modifies `.project-standards-audit` which blocks git push
- Absolute paths: `PROJECT_ROOT` defined at script top
- `pre-commit clean` + re-install needed after hook config changes

**Manual Full Validation** (run before push):
```bash
python scripts/validate-all.py --fix-auto
# Runs tests after each fix iteration
```