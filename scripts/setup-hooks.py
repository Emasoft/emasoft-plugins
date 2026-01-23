#!/usr/bin/env python3
"""setup-hooks.py - Install git hooks for marketplace and all submodules.

NEW ARCHITECTURE (v2):
======================
Problem: post-commit hooks fire on EVERY commit during rebase, causing
CHANGELOG.md to be regenerated mid-rebase, which causes conflicts.

Solution:
1. Remove post-commit hook entirely
2. Use post-rewrite hook (fires ONCE after rebase/amend completes)
3. Add rebase detection to pre-commit hook (skip during rebase)
4. Make changelog generation part of release workflow

Hook Summary:
- pre-commit: Lint, validate, version sync (skips during rebase)
- pre-push: Full validation, blocks broken plugins
- post-rewrite: Regenerate changelog after rebase/amend (fires once)
- post-merge: Regenerate changelog after merge

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
BLUE = "\033[0;34m"
NC = "\033[0m"


def check_git_cliff() -> bool:
    """Check if git-cliff is installed."""
    return shutil.which("git-cliff") is not None


def make_executable(path: Path) -> None:
    """Make a file executable."""
    current = os.stat(path)
    os.chmod(path, current.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_pre_commit_hook(hooks_dir: Path, repo_root: Path) -> None:
    """Create pre-commit hook for main repo with rebase detection."""
    source = repo_root / "scripts" / "pre-commit-hook.py"
    target = hooks_dir / "pre-commit"

    if source.exists():
        shutil.copy2(source, target)
        make_executable(target)
        print(f"{GREEN}✓{NC} Created pre-commit hook")
    else:
        print(f"{YELLOW}⚠{NC} pre-commit-hook.py not found, skipping")


def create_pre_push_hook(hooks_dir: Path, repo_root: Path) -> None:
    """Create pre-push hook for main repo."""
    source = repo_root / "scripts" / "pre-push-hook.py"
    target = hooks_dir / "pre-push"

    if source.exists():
        shutil.copy2(source, target)
        make_executable(target)
        print(f"{GREEN}✓{NC} Created pre-push hook")
    else:
        print(f"{YELLOW}⚠{NC} pre-push-hook.py not found, skipping")


def create_post_rewrite_hook(hooks_dir: Path, repo_name: str = "main repo") -> None:
    """Create post-rewrite hook for changelog generation after rebase/amend.

    post-rewrite fires ONCE after:
    - git rebase completes (all commits replayed)
    - git commit --amend completes

    This avoids the mid-rebase CHANGELOG conflicts.
    """
    hook_content = f'''#!/usr/bin/env python3
"""post-rewrite hook: Update CHANGELOG.md after rebase/amend completes.

This hook fires ONCE after rebase or amend operations complete,
avoiding the mid-rebase conflicts that post-commit causes.

Arguments passed by git:
- $1: "rebase" or "amend"
- stdin: list of rewritten commits (old-sha new-sha)
"""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    operation = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    if not shutil.which("git-cliff"):
        return 0  # Silent skip if git-cliff not installed

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    repo_root = Path(result.stdout.strip())

    cliff_toml = repo_root / "cliff.toml"
    if not cliff_toml.exists():
        return 0  # Silent skip if no cliff.toml

    print(f"[post-rewrite] Regenerating CHANGELOG.md after {{operation}}...")

    result = subprocess.run(
        ["git-cliff", "-o", "CHANGELOG.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(f"Warning: git-cliff failed: {{result.stderr}}")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    target = hooks_dir / "post-rewrite"
    target.write_text(hook_content)
    make_executable(target)
    print(f"{GREEN}✓{NC} Created post-rewrite hook ({repo_name})")


def create_post_merge_hook(hooks_dir: Path, repo_name: str = "main repo") -> None:
    """Create post-merge hook for changelog generation after merge."""
    hook_content = f'''#!/usr/bin/env python3
"""post-merge hook: Update CHANGELOG.md after merge completes."""

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if not shutil.which("git-cliff"):
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
        return 0

    print("[post-merge] Regenerating CHANGELOG.md...")

    result = subprocess.run(
        ["git-cliff", "-o", "CHANGELOG.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(f"Warning: git-cliff failed: {{result.stderr}}")
        return 0

    status = subprocess.run(
        ["git", "diff", "--quiet", "CHANGELOG.md"],
        cwd=repo_root,
        capture_output=True,
        timeout=30,
    )

    if status.returncode != 0:
        print("CHANGELOG.md updated - remember to commit it!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    target = hooks_dir / "post-merge"
    target.write_text(hook_content)
    make_executable(target)
    print(f"{GREEN}✓{NC} Created post-merge hook ({repo_name})")


def remove_old_post_commit_hook(hooks_dir: Path, repo_name: str = "main repo") -> None:
    """Remove the old post-commit hook that caused rebase conflicts."""
    post_commit = hooks_dir / "post-commit"
    if post_commit.exists():
        post_commit.unlink()
        print(f"{YELLOW}→{NC} Removed old post-commit hook ({repo_name})")


def setup_submodule_hooks(submodule_name: str, repo_root: Path) -> bool:
    """Set up hooks for a submodule."""
    hooks_dir = repo_root / ".git" / "modules" / submodule_name / "hooks"

    if not hooks_dir.exists():
        print(f"{RED}✗{NC} Submodule {submodule_name} not found or not initialized")
        return False

    # Remove old problematic post-commit hook
    remove_old_post_commit_hook(hooks_dir, submodule_name)

    # Install new hooks
    create_post_rewrite_hook(hooks_dir, submodule_name)
    create_post_merge_hook(hooks_dir, submodule_name)

    return True


def main() -> int:
    """Main setup function."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}Git Hooks Setup v2 - Rebase-Safe Architecture{NC}")
    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"Repository root: {repo_root}")
    print()

    # Check dependencies
    if not check_git_cliff():
        print(f"{YELLOW}Warning:{NC} git-cliff not installed. Install: brew install git-cliff")
    print()

    # Main repository hooks
    print(f"{BLUE}Main repository hooks{NC}")
    print("-" * 40)

    main_hooks_dir = repo_root / ".git" / "hooks"
    main_hooks_dir.mkdir(parents=True, exist_ok=True)

    # Remove old post-commit hook
    remove_old_post_commit_hook(main_hooks_dir, "main repo")

    # Install new hooks
    create_pre_commit_hook(main_hooks_dir, repo_root)
    create_pre_push_hook(main_hooks_dir, repo_root)
    create_post_rewrite_hook(main_hooks_dir, "main repo")
    create_post_merge_hook(main_hooks_dir, "main repo")

    # Submodule hooks
    print()
    print(f"{BLUE}Submodule hooks{NC}")
    print("-" * 40)

    setup_submodule_hooks("perfect-skill-suggester", repo_root)
    setup_submodule_hooks("claude-plugins-validation", repo_root)

    # Summary
    print()
    print(f"{GREEN}{'=' * 60}{NC}")
    print(f"{GREEN}All git hooks installed successfully!{NC}")
    print(f"{GREEN}{'=' * 60}{NC}")
    print()
    print("Hook architecture (v2 - rebase-safe):")
    print()
    print("  Main repo:")
    print("    pre-commit    → Lint, validate, version sync (skips during rebase)")
    print("    pre-push      → Full validation, blocks broken plugins")
    print("    post-rewrite  → Changelog after rebase/amend (fires ONCE)")
    print("    post-merge    → Changelog after merge")
    print()
    print("  Submodules:")
    print("    post-rewrite  → Changelog after rebase/amend (fires ONCE)")
    print("    post-merge    → Changelog after merge")
    print()
    print(f"{YELLOW}NOTE:{NC} post-commit hooks removed to prevent rebase conflicts.")
    print(f"      Changelog is now generated only after rebase/amend/merge completes.")
    print()
    print("Manual changelog generation:")
    print("    python scripts/generate-changelog.py [--all]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
