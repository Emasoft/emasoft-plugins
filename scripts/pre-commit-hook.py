#!/usr/bin/env python3
"""pre-commit-hook.py - Pre-commit validation for marketplace and plugins.

This script validates:
1. marketplace.json if changed
2. plugin.json files (JSON syntax, required fields, semver)
3. hooks.json files
4. Python files (linting)
5. Version consistency
6. Sensitive data patterns

IMPORTANT: This hook is SKIPPED during:
- git rebase (interactive or not)
- git cherry-pick
- git merge (during conflict resolution)
- git am (applying patches)

This prevents validation errors during history rewriting operations.

To install as git hook:
    cp scripts/pre-commit-hook.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ANSI Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def is_rebase_in_progress(git_dir: Path) -> bool:
    """Check if we're in the middle of a rebase or other history-rewriting operation.

    During rebase/cherry-pick/merge, commits are being replayed and we should
    skip validation to avoid conflicts and slowdowns.
    """
    # Check for rebase indicators
    rebase_indicators = [
        git_dir / "rebase-merge",      # git rebase (interactive)
        git_dir / "rebase-apply",       # git rebase (non-interactive) / git am
        git_dir / "CHERRY_PICK_HEAD",   # git cherry-pick
        git_dir / "MERGE_HEAD",         # git merge in progress
        git_dir / "BISECT_LOG",         # git bisect
    ]

    for indicator in rebase_indicators:
        if indicator.exists():
            return True

    # Also check environment variable (some git operations set this)
    if os.environ.get("GIT_AUTHOR_DATE"):
        # During rebase, git sets GIT_AUTHOR_DATE to preserve original timestamps
        # This is a secondary indicator
        pass  # Not conclusive on its own

    return False


def get_git_dir() -> Path:
    """Get the .git directory path (handles both regular repos and submodules)."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    # Fallback
    return Path(".git")


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    code, stdout, _ = run_command(["git", "diff", "--cached", "--name-only"])
    if code == 0:
        return [f for f in stdout.strip().split("\n") if f]
    return []


def get_staged_diff() -> str:
    """Get staged diff content."""
    code, stdout, _ = run_command(["git", "diff", "--cached", "-U0"])
    return stdout if code == 0 else ""


def validate_semver(version: str) -> bool:
    """Validate semver format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def validate_marketplace_json(repo_root: Path) -> tuple[bool, str]:
    """Validate marketplace.json."""
    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_marketplace.py"
    if not validator.exists():
        return True, "validator not found"

    code, stdout, stderr = run_command(
        ["uv", "run", "python", str(validator), str(repo_root)],
        cwd=repo_root / "claude-plugins-validation"
    )
    if code == 0:
        return True, ""
    return False, "Run: uv run python scripts/validate_marketplace.py . --verbose"


def validate_plugin_json(file_path: Path) -> tuple[bool, str]:
    """Validate a plugin.json file."""
    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e}"

    name = data.get("name")
    version = data.get("version")

    if not name:
        return False, "missing 'name' field"
    if not version:
        return False, "missing 'version' field"
    if not validate_semver(version):
        return False, f"invalid version format: {version}"

    return True, ""


def validate_hooks_json(file_path: Path, repo_root: Path) -> tuple[bool, str]:
    """Validate a hooks.json file."""
    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_hook.py"

    if validator.exists():
        code, _, _ = run_command(
            ["uv", "run", "python", str(validator), str(file_path), "--quiet"],
            cwd=repo_root / "claude-plugins-validation"
        )
        if code == 0:
            return True, ""
        return True, "has issues (non-blocking)"  # Non-blocking, still return True

    # Fallback: just check JSON validity
    try:
        with open(file_path) as f:
            json.load(f)
        return True, "JSON valid"
    except json.JSONDecodeError:
        return False, "invalid JSON"


def lint_python_files(files: list[str], repo_root: Path) -> tuple[bool, str]:
    """Lint Python files with ruff."""
    existing_files = [f for f in files if (repo_root / f).exists()]
    if not existing_files:
        return True, "no files to lint"

    code, _, _ = run_command(
        ["uv", "run", "ruff", "check"] + existing_files,
        cwd=repo_root
    )
    if code == 0:
        return True, ""
    return False, "linting issues (non-blocking)"


def check_version_consistency(repo_root: Path) -> tuple[bool, bool]:
    """Check version consistency. Returns (passed, was_fixed)."""
    sync_script = repo_root / "scripts" / "sync-versions.py"
    if not sync_script.exists():
        return True, False

    code, _, _ = run_command(
        ["python3", str(sync_script), "--check", str(repo_root)],
        cwd=repo_root
    )
    if code == 0:
        return True, False

    # Auto-fix by syncing
    run_command(["python3", str(sync_script), str(repo_root)], cwd=repo_root)

    # Stage the updated marketplace.json
    marketplace_json = repo_root / ".claude-plugin" / "marketplace.json"
    if marketplace_json.exists():
        run_command(["git", "add", str(marketplace_json)], cwd=repo_root)
        return True, True

    return True, True


def check_sensitive_data(diff: str) -> bool:
    """Check for sensitive data patterns in diff."""
    patterns = [
        r"password\s*[:=]",
        r"api[_-]?key\s*[:=]",
        r"secret\s*[:=]",
        r"token\s*[:=].*['\"][a-zA-Z0-9]{20,}['\"]",
        r"private[_-]?key",
    ]

    for line in diff.split("\n"):
        # Skip removed lines
        if line.startswith("-"):
            continue
        # Skip obvious placeholders
        if any(x in line.lower() for x in ["example", "placeholder", "your_", "<", "todo"]):
            continue

        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
    return False


def main() -> int:
    """Main pre-commit hook function."""
    # Get git directory and check for rebase
    git_dir = get_git_dir()

    if is_rebase_in_progress(git_dir):
        print(f"{BLUE}[pre-commit] Skipping validation during rebase/cherry-pick/merge{NC}")
        return 0  # Allow commit to proceed without validation

    repo_root = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    ).stdout.strip())

    print("Running pre-commit validations...")

    validation_failed = False
    staged_files = get_staged_files()

    # 1. Validate marketplace.json if changed
    if any("marketplace.json" in f for f in staged_files):
        print("Validating marketplace.json... ", end="", flush=True)
        passed, msg = validate_marketplace_json(repo_root)
        if passed:
            print(f"{GREEN}✔{NC}")
        else:
            print(f"{RED}✘{NC}")
            print(f"{RED}Marketplace validation failed. {msg}{NC}")
            validation_failed = True

    # 2. Validate changed plugin.json files
    plugin_jsons = [f for f in staged_files if f.endswith("plugin.json")]
    for plugin_json in plugin_jsons:
        file_path = repo_root / plugin_json
        if file_path.exists():
            print(f"Validating {plugin_json}... ", end="", flush=True)
            passed, msg = validate_plugin_json(file_path)
            if passed:
                print(f"{GREEN}✔{NC}")
            else:
                print(f"{RED}✘ {msg}{NC}")
                validation_failed = True

    # 3. Validate changed hooks.json files
    hooks_jsons = [f for f in staged_files if f.endswith("hooks.json")]
    for hooks_json in hooks_jsons:
        file_path = repo_root / hooks_json
        if file_path.exists():
            print(f"Validating {hooks_json}... ", end="", flush=True)
            passed, msg = validate_hooks_json(file_path, repo_root)
            if passed:
                print(f"{GREEN}✔{NC}" + (f" ({msg})" if msg else ""))
            else:
                print(f"{YELLOW}⚠ {msg}{NC}")

    # 4. Lint changed Python files
    py_files = [f for f in staged_files if f.endswith(".py")]
    if py_files:
        print("Linting Python files... ", end="", flush=True)
        passed, msg = lint_python_files(py_files, repo_root)
        if passed:
            print(f"{GREEN}✔{NC}" + (f" ({msg})" if msg else ""))
        else:
            print(f"{YELLOW}⚠ {msg}{NC}")

    # 5. Check version consistency
    print("Checking version consistency... ", end="", flush=True)
    passed, was_fixed = check_version_consistency(repo_root)
    if passed and not was_fixed:
        print(f"{GREEN}✔{NC}")
    elif was_fixed:
        print(f"{YELLOW}⚠ versions out of sync, syncing...{NC}")
        print("  Staged updated marketplace.json")
    else:
        print(f"{YELLOW}⚠ sync script not found{NC}")

    # 6. Check for sensitive data
    print("Checking for sensitive data... ", end="", flush=True)
    diff = get_staged_diff()
    if check_sensitive_data(diff):
        print(f"{YELLOW}⚠ potential sensitive data detected - please review{NC}")
    else:
        print(f"{GREEN}✔{NC}")

    # Final result
    if validation_failed:
        print()
        print(f"{RED}Pre-commit validation failed. Please fix the issues above.{NC}")
        print("To bypass (not recommended): git commit --no-verify")
        return 1

    print(f"{GREEN}Pre-commit validations passed{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
