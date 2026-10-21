# Tool Versions & CLI vs Module Matrix

## Tested Versions (Hermes Python 3.14.7)

| Tool | Version | CLI Command | Python Module | Notes |
|------|---------|-------------|---------------|-------|
| ruff | 0.17.0 | `ruff` | `python -m ruff` | Both work |
| pyright | 1.1.414 | `pyright` | `python -m pyright` | Both work |
| bandit | 1.9.4 | `bandit` | `python -m bandit` | Both work |
| radon | 6.0.1 | `radon` | `python -m radon` | Both work |
| semgrep | 1.180.0 | `semgrep` | ❌ | CLI only (deprecated python -m) |
| pip-audit | 2.10.1 | `pip-audit` | ❌ | CLI only |
| vulture | 2.16 | `vulture` | `python -m vulture` | Both work |

## Resolution Logic

```python
# parsers/base.py:_resolve_tool_path()
1. Check PATH via shutil.which(tool_name)
2. Check tool_aliases: semgrep→pysemgrep, pip-audit→pip-audit
3. Fallback: Path(sys.executable).parent / actual_tool_name
4. For pip-audit: try pip-audit, pip_audit, pip-audit.exe
```

## Hermes Environment Path

Tools installed at:
`/home/hermes/.hermes/tools/python-3.14.7+<hash>/lib/python3.14/site-packages/`

Binaries at:
`/home/hermes/.hermes/tools/python-3.14.7+<hash>/bin/`

## Pre-Commit Wrapper Pattern

When running validate-all.py or similar scripts via pre-commit hooks:

1. **Filesystem restrictions**: pre-commit's `language: script` hooks may fail with "file not found" when executing repo scripts directly
2. **Wrapper pattern**: Copy script to temp location before executing

```bash
# .pre-commit-hooks/validate-all-skip-tests
#!/bin/bash
export VALIDATE_ALL_SKIP_TESTS=1
TMP_SCRIPT=$(mktemp --suffix=.py)
cp "$PROJECT_ROOT/scripts/validate-all.py" "$TMP_SCRIPT"
exec python "$TMP_SCRIPT" "$@"
```

3. **Environment variable for flags**: Use env var instead of CLI flag for pre-commit compatibility

```bash
export VALIDATE_ALL_SKIP_TESTS=1
```

4. **Hook receives 0 arguments**: With `pass_filenames: false`, pre-commit calls hook with no arguments

## Verification Command

```bash
for t in ruff pyright bandit radon semgrep pip-audit vulture; do
  echo -n "$t: "
  python -m $t --version 2>/dev/null || $t --version 2>/dev/null || echo "NOT FOUND"
done
```

## Upgrade Procedure

1. `pip install --upgrade <tool>` in Hermes Python env
2. Cache auto-invalidates (tool version in cache key)
3. Run gate to verify
4. Update this table
