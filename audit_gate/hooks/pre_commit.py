"""Pre-commit hook for audit_gate."""

import sys
from pathlib import Path

from ..cli import gate
from ..core.thresholds import SECURITY_TOOLS


def main():
    """Pre-commit hook - runs fast security-only gate."""
    # For pre-commit, we only run security tools (fast)
    import sys
    sys.argv = ["audit_gate", "gate", ".", "--tools", "bandit,semgrep,pip_audit", "--format", "text"]
    
    from ..cli import cli
    cli(standalone_mode=False)


if __name__ == "__main__":
    main()
