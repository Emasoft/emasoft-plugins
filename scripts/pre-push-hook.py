#!/usr/bin/env python3
"""pre-push-hook.py - Validate the current repo before allowing git push.

Installed as .git/hooks/pre-push in any plugin or marketplace repo.
Uses CPV (claude-plugins-validation) from the plugin cache with --strict.
Validates the LOCAL repo (the one being pushed), blocking if any issues found.

To install:
    python3 scripts/setup-hooks.py
    # OR manually:
    cp scripts/pre-push-hook.py .git/hooks/pre-push
    chmod +x .git/hooks/pre-push

Exit codes:
    0 - All validations passed, push allowed
    1 - Validation failed, push blocked
"""

import os
import subprocess
import sys
from pathlib import Path

# ANSI Colors
_USE_COLOR = (
    not os.environ.get("NO_COLOR")
    and os.name != "nt"
    and hasattr(sys.stdout, "isatty")
    and sys.stdout.isatty()
)
RED = "\033[0;31m" if _USE_COLOR else ""
GREEN = "\033[0;32m" if _USE_COLOR else ""
YELLOW = "\033[1;33m" if _USE_COLOR else ""
BLUE = "\033[0;34m" if _USE_COLOR else ""
BOLD = "\033[1m" if _USE_COLOR else ""
NC = "\033[0m" if _USE_COLOR else ""


def find_cpv_dir() -> Path | None:
    """Find the CPV plugin directory from the installed plugin cache."""
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "emasoft-plugins" / "claude-plugins-validation"
    if not cache_base.is_dir():
        return None
    # Get latest version directory by sorting version strings
    versions = sorted(
        [d for d in cache_base.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    if not versions:
        return None
    latest = versions[-1]
    if (latest / "scripts" / "validate_plugin.py").is_file():
        return latest
    return None


def get_repo_root() -> Path:
    """Return the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def is_marketplace(repo_root: Path) -> bool:
    """Check if this repo is a marketplace (has marketplace.json)."""
    return (repo_root / ".claude-plugin" / "marketplace.json").is_file()


def is_plugin(repo_root: Path) -> bool:
    """Check if this repo is a plugin (has plugin.json)."""
    return (repo_root / ".claude-plugin" / "plugin.json").is_file()


def run_validator(
    cpv_dir: Path,
    script_name: str,
    target: Path,
    timeout: int = 120,
) -> tuple[int, str]:
    """Run a CPV validation script with --strict. Returns (exit_code, output)."""
    script = cpv_dir / "scripts" / script_name
    if not script.is_file():
        return -1, f"Validator not found: {script}"

    cmd = ["uv", "run", "python", str(script), str(target), "--strict"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout,
            cwd=str(cpv_dir),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT: {script_name} exceeded {timeout}s"
    except FileNotFoundError:
        return -1, "uv not found — install uv first"


def main() -> int:
    repo_root = get_repo_root()

    print(f"{BOLD}{'=' * 60}{NC}")
    print(f"{BOLD}Pre-Push Validation (--strict){NC}")
    print(f"{BOLD}{'=' * 60}{NC}")
    print()

    # Find CPV
    cpv_dir = find_cpv_dir()
    if cpv_dir is None:
        print(f"{RED}ERROR: CPV plugin not found in cache.{NC}")
        print("Install it: claude /cpv-install-plugin claude-plugins-validation")
        return 1

    print(f"{BLUE}Repo:{NC}     {repo_root}")
    print(f"{BLUE}CPV:{NC}      {cpv_dir}")
    print()

    # Detect what kind of repo this is and validate accordingly
    if is_marketplace(repo_root):
        print(f"{BLUE}Detected: marketplace repo{NC}")
        print(f"{BLUE}Validating marketplace.json with --strict...{NC}")
        code, output = run_validator(cpv_dir, "validate_marketplace.py", repo_root)
    elif is_plugin(repo_root):
        print(f"{BLUE}Detected: plugin repo{NC}")
        print(f"{BLUE}Validating plugin with --strict...{NC}")
        code, output = run_validator(cpv_dir, "validate_plugin.py", repo_root)
    else:
        print(f"{YELLOW}Not a plugin or marketplace repo. Skipping validation.{NC}")
        return 0

    # Show relevant output lines
    for line in output.splitlines():
        if any(sev in line for sev in ("CRITICAL", "MAJOR", "MINOR", "NIT", "PASSED", "Plugin Validation", "Marketplace Validation")):
            print(f"  {line.strip()}")

    # Verdict
    print()
    print(f"{BOLD}{'=' * 60}{NC}")
    if code == 0:
        print(f"{GREEN}  PASSED — push allowed{NC}")
        print(f"{BOLD}{'=' * 60}{NC}")
        return 0
    else:
        print(f"{RED}  BLOCKED — validation issues found (exit {code}){NC}")
        print(f"{RED}  Fix ALL issues before pushing.{NC}")
        print(f"{BOLD}{'=' * 60}{NC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
