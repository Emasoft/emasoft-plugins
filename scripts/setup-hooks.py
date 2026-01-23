#!/usr/bin/env python3
"""setup-hooks.py - Install git hooks for marketplace and all submodules.

Run this after cloning to set up all git hooks.

Usage:
    python scripts/setup-hooks.py
"""

import os
import shutil
import stat
import sys
from pathlib import Path

# ANSI Colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def check_git_cliff() -> bool:
    """Check if git-cliff is installed."""
    return shutil.which("git-cliff") is not None


def make_executable(path: Path) -> None:
    """Make a file executable."""
    current = os.stat(path)
    os.chmod(path, current.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_pre_commit_hook(hooks_dir: Path, repo_root: Path) -> None:
    """Create pre-commit hook for main repo."""
    # Copy the Python pre-commit hook
    source = repo_root / "scripts" / "pre-commit-hook.py"
    target = hooks_dir / "pre-commit"

    if source.exists():
        shutil.copy2(source, target)
        make_executable(target)
        print(f"{GREEN}✓{NC} Created main repo pre-commit hook (Python)")
    else:
        print(f"{YELLOW}⚠{NC} pre-commit-hook.py not found, skipping")


def create_pre_push_hook(hooks_dir: Path, repo_root: Path) -> None:
    """Create pre-push hook for main repo to block broken plugins."""
    # Copy the Python pre-push hook
    source = repo_root / "scripts" / "pre-push-hook.py"
    target = hooks_dir / "pre-push"

    if source.exists():
        shutil.copy2(source, target)
        make_executable(target)
        print(f"{GREEN}✓{NC} Created main repo pre-push hook (Python)")
    else:
        print(f"{YELLOW}⚠{NC} pre-push-hook.py not found, skipping")


def create_post_commit_hook(hooks_dir: Path, submodule_name: str | None = None) -> None:
    """Create post-commit hook for changelog generation."""
    hook_content = '''#!/usr/bin/env python3
"""post-commit hook: Update CHANGELOG.md using git-cliff."""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if not shutil.which("git-cliff"):
        print("Warning: git-cliff not found, skipping changelog generation")
        return 0

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    repo_root = Path(result.stdout.strip())

    cliff_toml = repo_root / "cliff.toml"
    if not cliff_toml.exists():
        print("Warning: cliff.toml not found, skipping changelog generation")
        return 0

    name = "''' + (submodule_name or "main repo") + """"
    print(f"Generating CHANGELOG.md for {name}...")

    result = subprocess.run(
        ["git-cliff", "-o", "CHANGELOG.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(f"Warning: git-cliff failed: {result.stderr}")
        return 0

    # Check if changelog changed
    status = subprocess.run(
        ["git", "diff", "--quiet", "CHANGELOG.md"],
        cwd=repo_root,
        capture_output=True,
        timeout=30,
    )

    if status.returncode != 0:
        print("CHANGELOG.md updated - remember to commit it!")
    else:
        print("CHANGELOG.md is up to date")

    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

    target = hooks_dir / "post-commit"
    target.write_text(hook_content)
    make_executable(target)

    label = submodule_name or "main repo"
    print(f"{GREEN}✓{NC} Created {label} post-commit hook")


def setup_submodule_hooks(submodule_name: str, repo_root: Path) -> bool:
    """Set up hooks for a submodule."""
    hooks_dir = repo_root / ".git" / "modules" / submodule_name / "hooks"

    if not hooks_dir.exists():
        print(f"{RED}✗{NC} Submodule {submodule_name} not found or not initialized")
        return False

    create_post_commit_hook(hooks_dir, submodule_name)
    return True


def main() -> int:
    """Main setup function."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    print("Setting up git hooks for emasoft-plugins-marketplace...")
    print(f"Repository root: {repo_root}")
    print()

    # Check dependencies
    if not check_git_cliff():
        print(f"{YELLOW}Warning:{NC} git-cliff is not installed. Install it with: brew install git-cliff")
    print()

    # Main repository hooks
    print("=" * 60)
    print("Main repository hooks")
    print("=" * 60)

    main_hooks_dir = repo_root / ".git" / "hooks"
    main_hooks_dir.mkdir(parents=True, exist_ok=True)

    create_pre_commit_hook(main_hooks_dir, repo_root)
    create_pre_push_hook(main_hooks_dir, repo_root)
    create_post_commit_hook(main_hooks_dir)

    # Submodule hooks
    print()
    print("=" * 60)
    print("Submodule hooks")
    print("=" * 60)

    setup_submodule_hooks("perfect-skill-suggester", repo_root)
    setup_submodule_hooks("claude-plugins-validation", repo_root)

    # Summary
    print()
    print("All git hooks have been set up successfully!")
    print()
    print("Hook summary:")
    print("  Main repo:")
    print("    - pre-commit: Validates and syncs plugin versions (Python)")
    print("    - pre-push: Blocks pushing broken plugins to GitHub (Python)")
    print("    - post-commit: Generates CHANGELOG.md with git-cliff (Python)")
    print("  Submodules:")
    print("    - post-commit: Generates CHANGELOG.md with git-cliff (Python)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
