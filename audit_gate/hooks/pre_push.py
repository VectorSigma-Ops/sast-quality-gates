"""Pre-push hook for audit_gate with auto-fix."""

import sys
from pathlib import Path

from ..core.thresholds import SECURITY_TOOLS


def main():
    """Pre-push hook - runs full gate with auto-fix."""
    import sys
    sys.argv = [
        "audit_gate", "gate", ".",
        "--format", "text",
        "--tools", "ruff,pyright,bandit,radon,semgrep,pip_audit,vulture"
    ]
    
    from ..cli import cli
    cli(standalone_mode=False)


if __name__ == "__main__":
    main()
