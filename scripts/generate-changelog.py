#!/usr/bin/env python3
"""generate-changelog.py - Manually generate CHANGELOG.md using git-cliff.

This script replaces the automatic post-commit changelog generation
that caused conflicts during rebases.

Usage:
    python scripts/generate-changelog.py          # Generate for current repo
    python scripts/generate-changelog.py --all    # Generate for all (main + submodules)
    python scripts/generate-changelog.py --commit # Generate and commit changes
"""

import argparse
import shutil
import subprocess
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


def generate_changelog(repo_path: Path, name: str = "repo") -> bool:
    """Generate CHANGELOG.md for a repository.

    Returns True if changelog was updated, False if unchanged or error.
    """
    cliff_toml = repo_path / "cliff.toml"
    if not cliff_toml.exists():
        print(f"{YELLOW}⚠{NC} {name}: No cliff.toml found, skipping")
        return False

    print(f"{BLUE}→{NC} Generating CHANGELOG.md for {name}...")

    result = subprocess.run(
        ["git-cliff", "-o", "CHANGELOG.md"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        print(f"{RED}✘{NC} {name}: git-cliff failed: {result.stderr}")
        return False

    # Check if changelog changed
    status = subprocess.run(
        ["git", "diff", "--quiet", "CHANGELOG.md"],
        cwd=repo_path,
        capture_output=True,
        timeout=30
    )

    if status.returncode != 0:
        print(f"{GREEN}✓{NC} {name}: CHANGELOG.md updated")
        return True
    else:
        print(f"{GREEN}✓{NC} {name}: CHANGELOG.md unchanged")
        return False


def commit_changelog(repo_path: Path, name: str = "repo") -> bool:
    """Commit the updated CHANGELOG.md."""
    # Check if there are changes
    status = subprocess.run(
        ["git", "diff", "--quiet", "CHANGELOG.md"],
        cwd=repo_path,
        capture_output=True,
        timeout=30
    )

    if status.returncode == 0:
        return False  # No changes

    # Stage and commit
    subprocess.run(["git", "add", "CHANGELOG.md"], cwd=repo_path, timeout=30)
    result = subprocess.run(
        ["git", "commit", "-m", "chore: Update CHANGELOG.md"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30
    )

    if result.returncode == 0:
        print(f"{GREEN}✓{NC} {name}: Committed CHANGELOG.md")
        return True
    else:
        print(f"{YELLOW}⚠{NC} {name}: Commit failed (maybe nothing to commit)")
        return False


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG.md using git-cliff"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for main repo and all submodules"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit the updated CHANGELOG.md files"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository (default: current directory)"
    )

    args = parser.parse_args()

    if not check_git_cliff():
        print(f"{RED}Error:{NC} git-cliff is not installed")
        print("Install with: brew install git-cliff")
        return 1

    repo_root = Path(args.path).resolve()

    print(f"{BLUE}{'=' * 50}{NC}")
    print(f"{BLUE}Changelog Generation{NC}")
    print(f"{BLUE}{'=' * 50}{NC}")
    print()

    updated = []

    # Generate for main repo
    if generate_changelog(repo_root, "main repo"):
        updated.append(("main repo", repo_root))

    # Generate for submodules if --all
    if args.all:
        submodules = [
            "perfect-skill-suggester",
            "claude-plugins-validation"
        ]
        for submodule in submodules:
            submodule_path = repo_root / submodule
            if submodule_path.exists() and (submodule_path / ".git").exists():
                if generate_changelog(submodule_path, submodule):
                    updated.append((submodule, submodule_path))
            elif submodule_path.exists():
                # Submodule might be using worktree (check for .git file)
                git_file = submodule_path / ".git"
                if git_file.is_file():
                    if generate_changelog(submodule_path, submodule):
                        updated.append((submodule, submodule_path))

    # Commit if requested
    if args.commit and updated:
        print()
        print(f"{BLUE}Committing changes...{NC}")
        for name, path in updated:
            commit_changelog(path, name)

    # Summary
    print()
    if updated:
        print(f"{GREEN}Updated {len(updated)} changelog(s){NC}")
        if not args.commit:
            print(f"{YELLOW}Run with --commit to commit the changes{NC}")
    else:
        print(f"{GREEN}All changelogs are up to date{NC}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
