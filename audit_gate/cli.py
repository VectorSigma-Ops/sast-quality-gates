"""CLI entry point for audit_gate."""

import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import click

from .core.gate import GateEvaluator, GateReport, ToolResult
from .core.thresholds import DEFAULT_THRESHOLDS, DEFAULT_GLOBAL
from .parsers import base
from .core.finding import Finding, Severity, ToolStatus


# Import all parsers
from .parsers import ruff, pyright, bandit, radon, semgrep, pip_audit, vulture


# Parser registry
PARSERS = {
    "ruff": ruff.RuffParser(),
    "pyright": pyright.PyrightParser(),
    "bandit": bandit.BanditParser(),
    "radon": radon.RadonParser(),
    "semgrep": semgrep.SemgrepParser(),
    "pip_audit": pip_audit.PipAuditParser(),
    "vulture": vulture.VultureParser(),
}


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """audit_gate - Multi-tool SAST quality gates with auto-fix."""
    pass


@cli.command()
@click.argument("dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json", "github", "sarif"]), default="text")
@click.option("--tools", help="Comma-separated list of tools to run (default: all)")
@click.option("--config", type=click.Path(exists=True), help="Gate config YAML file")
@click.option("--fail-fast", is_flag=True, help="Exit on first failure")
@click.option("--cache/--no-cache", default=True, help="Enable/disable caching")
def gate(dir: Path, fmt: str, tools: str, config: str, fail_fast: bool, cache: bool):
    """Run SAST quality gate on directory."""
    
    # Parse tool list
    tool_names = [t.strip() for t in tools.split(",")] if tools else list(PARSERS.keys())
    
    # Find Python files
    py_files = list(dir.rglob("*.py"))
    if not py_files:
        click.echo("No Python files found", err=True)
        sys.exit(1)
    
    # Filter parsers
    parsers = [PARSERS[t] for t in tool_names if t in PARSERS]
    
    # Run all tools on all files
    results = []
    start_time = time.time()
    
    for parser in parsers:
        tool_start = time.time()
        tool_findings = []
        
        for py_file in py_files:
            status, findings, error = parser.run(py_file)
            if status == ToolStatus.NOT_INSTALLED:
                # Tool not installed
                results.append(ToolResult(
                    tool=parser.tool_name,
                    status=ToolStatus.NOT_INSTALLED,
                    findings=[],
                    error=error,
                    duration_ms=0
                ))
                break
            elif status == ToolStatus.FAILED:
                results.append(ToolResult(
                    tool=parser.tool_name,
                    status=ToolStatus.FAILED,
                    findings=[],
                    error=error,
                    duration_ms=0
                ))
                if click.get_current_context().params.get("fail_fast"):
                    break
            else:
                tool_findings.extend(findings)
        
        if any(r.tool == parser.tool_name for r in results):
            continue
            
        duration_ms = (time.time() - tool_start) * 1000
        results.append(ToolResult(
            tool=parser.tool_name,
            status=ToolStatus.SUCCESS,
            findings=tool_findings,
            duration_ms=duration_ms
        ))
    
    # Evaluate gate
    evaluator = GateEvaluator()
    report = evaluator.evaluate(results)
    
    # Output
    if fmt == "json":
        output = {
            "passed": report.passed,
            "total_findings": report.total_findings,
            "by_tool": report.by_tool,
            "by_severity": report.by_severity,
            "duration_ms": report.duration_ms,
            "results": [
                {
                    "tool": r.tool,
                    "status": r.status.value,
                    "findings": [f.to_dict() for f in r.findings],
                    "error": r.error,
                    "duration_ms": r.duration_ms
                }
                for r in results
            ],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Text output
        click.echo(f"Gate: {'PASS' if report.passed else 'FAIL'}")
        click.echo(f"Total findings: {report.total_findings}")
        for tool, count in report.by_tool.items():
            click.echo(f"  {tool}: {count}")
        for severity, count in report.by_severity.items():
            if count > 0:
                click.echo(f"  {severity}: {count}")
    
    if not report.passed:
        sys.exit(1)


@cli.command()
@click.argument("dir", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
@click.option("--tools", help="Comma-separated list of tools to run")
def check_tools(dir: Path, tools: str):
    """Verify all SAST tools are installed and functional."""
    tool_names = [t.strip() for t in tools.split(",")] if tools else list(PARSERS.keys())
    
    click.echo("Verifying SAST tools...")
    all_ok = True
    
    for name in tool_names:
        if name not in PARSERS:
            click.echo(f"  ❌ {name}: Unknown tool")
            all_ok = False
            continue
            
        parser = PARSERS[name]
        version = parser.get_version()
        if version != "unknown":
            click.echo(f"  ✅ {name}: {version}")
        else:
            click.echo(f"  ❌ {name}: NOT INSTALLED")
            all_ok = False
    
    if not all_ok:
        sys.exit(1)
    click.echo("\n✅ All tools verified")


@cli.command()
@click.argument("tag", type=str)
def validate_release(tag: str):
    """Validate release tag format."""
    import re
    
    # Expected format: project-vX.Y.Z[-prerelease]
    pattern = r"^([a-z0-9-]+)-v(\d+)\.(\d+)\.(\d+)(?:-([a-z]+\.?\d*))?$"
    match = re.match(pattern, tag)
    
    if not match:
        click.echo(f"❌ Tag '{tag}' does not match format: project-vX.Y.Z[-prerelease]", err=True)
        sys.exit(1)
    
    project, major, minor, patch, prerelease = match.groups()
    
    click.echo(f"✅ Tag '{tag}' is valid")
    click.echo(f"  Project: {project}")
    click.echo(f"  Version: {major}.{minor}.{patch}")
    if prerelease:
        click.echo(f"  Prerelease: {prerelease}")




@cli.command()
@click.argument("commit_file", type=click.Path(exists=True, path_type=Path))
@click.option("--fix", is_flag=True, help="Auto-fix commit message")
def validate_commit(commit_file: Path, fix: bool):
    """Validate commit message format."""
    import re
    
    message = commit_file.read_text().strip()
    
    # Expected format: type(scope): subject
    pattern = r"^([a-z]+)\(([a-z0-9-]+)\): (.{1,72})$"
    match = re.match(pattern, message.split("\n")[0])
    
    if not match:
        click.echo(f"❌ Invalid commit message format", err=True)
        click.echo("Expected: type(scope): subject", err=True)
        if fix:
            lines = message.split("\n")
            first = lines[0]
            if not re.match(r"^[a-z]+\([a-z0-9-]+\):", first):
                fixed = "chore(core): " + first
                lines[0] = fixed
                fixed_message = "\n".join(lines)
                commit_file.write_text(fixed_message + "\n")
                click.echo("✅ Commit message fixed", err=True)
                return
        sys.exit(1)
    
    commit_type, scope, subject = match.groups()
    
    valid_types = {"feat", "fix", "docs", "style", "refactor", "test", "chore", "build", "ci", "perf"}
    if commit_type not in valid_types:
        click.echo(f"❌ Invalid type '{commit_type}'. Valid: {', '.join(sorted(valid_types))}", err=True)
        sys.exit(1)
    
    if not scope:
        click.echo("❌ Scope cannot be empty", err=True)
        sys.exit(1)
    
    if len(subject) > 72:
        click.echo(f"❌ Subject too long ({len(subject)} > 72 chars)", err=True)
        sys.exit(1)
    
    click.echo("✅ Commit message valid")
    if fix:
        click.echo("✅ Commit message valid after fix")

if __name__ == "__main__":
    cli()
