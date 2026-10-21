# Confidence Thresholds Reference

## Per-Fixer Confidence Values

| Fixer | Confidence | Type | Rationale |
|-------|-----------|------|-----------|
| ruff | 0.95 | Deterministic | Ruff --fix is safe, idempotent, well-tested |
| vulture | 0.9 | Semi-deterministic | False positives possible; _is_really_unused() mitigates |
| pip_audit | 0.9 | Deterministic | Version pinning is safe, reversible |
| bandit | 0.85 | Semi-deterministic | Pattern-based fixes; some context needed |
| pyright | 0.75 | Semi-deterministic | Type inference fixes; undefined var → SKIPPED |
| semgrep | 0.6 | LLM-assisted | Rule-dependent; needs human review |
| radon | 0.4 | LLM-assisted | Complexity reduction requires redesign |

## Threshold Logic

- Default `confidence_threshold = 0.8`
- Only fixers with confidence ≥ 0.8 auto-apply
- **Auto-applied**: ruff, vulture, pip_audit, bandit
- **Human review required**: pyright (0.75), semgrep (0.6), radon (0.4)

## Rationale by Fixer

### Ruff (0.95)
- Uses `ruff check --fix` which is battle-tested
- Idempotent: running twice produces same result
- Covers: imports, formatting, simple refactors

### Vulture (0.9)
- False positive rate ~10% without usage check
- `_is_really_unused()` AST verification reduces to <1%
- Adds `# noqa: F841` only when truly unused

### Pip-Audit (0.9)
- Only pins vulnerable deps to fixed versions
- Reversible: `pip install pkg==old` restores
- No code logic changes

### Bandit (0.85)
- Pattern-based: SQL injection → parameterized queries
- Shell injection → subprocess with list args
- Some fixes need context (e.g., hardcoded secrets)

### Pyright (0.75)
- **Undefined variable**: returns SKIPPED (never inject `var = None`)
- **Missing imports**: can auto-add if single candidate
- **Type ignores**: adds `# type: ignore` only with high confidence

### Semgrep (0.6)
- Rule quality varies widely
- Some rules are informational, not actionable
- LLM assists in understanding fix context

### Radon (0.4)
- Cyclomatic complexity > 10 needs architectural change
- Extracting methods changes call signatures
- Requires human design decisions

## Tuning Guide

- **Strict CI**: threshold=0.9 (only ruff, vulture, pip_audit)
- **Balanced**: threshold=0.8 (default, +bandit)
- **Aggressive**: threshold=0.6 (+pyright, semgrep)
- **Max auto-fix**: threshold=0.4 (all, but radon still risky)

## FixLoopConfig Defaults

```python
FixLoopConfig(
    max_iterations=2,
    max_fixes_per_iteration=10,
    confidence_threshold=0.8,
    run_tests_on_fix=False,
    excluded_patterns=[
        "**/hooks/*",
        "**/patches/*",
        "**/tests/**",
        "**/scripts/**",
    ],
)
```
