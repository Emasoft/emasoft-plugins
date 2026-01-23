#!/usr/bin/env python3
"""
Sync plugin versions from submodules to marketplace.json.

This script reads the version from each plugin's manifest and updates
the corresponding entry in marketplace.json. Supports multiple version sources:
- .claude-plugin/plugin.json (standard Claude Code plugin)
- pyproject.toml (Python projects)
- package.json (Node.js projects)

Run this after updating submodules to keep versions in sync.

Usage:
    python scripts/sync-versions.py [--check] [--verbose]

Options:
    --check     Check for version mismatches without updating (exit 1 if mismatch)
    --verbose   Show detailed output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def get_plugin_version(plugin_dir: Path) -> str | None:
    """Get the version from a plugin directory.

    Checks multiple sources in order of priority:
    1. .claude-plugin/plugin.json (standard Claude Code plugin)
    2. pyproject.toml (Python projects)
    3. package.json (Node.js projects)
    """
    # Try .claude-plugin/plugin.json first
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        try:
            with open(plugin_json, encoding="utf-8") as f:
                data = json.load(f)
                version = data.get("version")
                if version:
                    return version
        except (OSError, json.JSONDecodeError):
            pass

    # Try pyproject.toml (Python projects)
    pyproject = plugin_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, encoding="utf-8") as f:
                content = f.read()
                # Simple regex to extract version from [project] section
                match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                if match:
                    return match.group(1)
        except OSError:
            pass

    # Try package.json (Node.js projects)
    package_json = plugin_dir / "package.json"
    if package_json.exists():
        try:
            with open(package_json, encoding="utf-8") as f:
                data = json.load(f)
                version = data.get("version")
                if version:
                    return version
        except (OSError, json.JSONDecodeError):
            pass

    return None


def load_marketplace(marketplace_path: Path) -> dict | None:
    """Load marketplace.json."""
    try:
        with open(marketplace_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading marketplace.json: {e}", file=sys.stderr)
        return None


def save_marketplace(marketplace_path: Path, data: dict) -> bool:
    """Save marketplace.json with proper formatting."""
    try:
        with open(marketplace_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        return True
    except OSError as e:
        print(f"Error saving marketplace.json: {e}", file=sys.stderr)
        return False


def sync_versions(
    repo_root: Path,
    check_only: bool = False,
    verbose: bool = False,
) -> tuple[int, list[tuple[str, str, str]]]:
    """
    Sync plugin versions from submodules to marketplace.json.

    Args:
        repo_root: Path to marketplace repository root
        check_only: If True, only check for mismatches without updating
        verbose: If True, show detailed output

    Returns:
        Tuple of (exit_code, list of (plugin_name, old_version, new_version))
    """
    # Find marketplace.json
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        marketplace_path = repo_root / "marketplace.json"

    if not marketplace_path.exists():
        print("Error: marketplace.json not found", file=sys.stderr)
        return 1, []

    # Load marketplace data
    marketplace = load_marketplace(marketplace_path)
    if marketplace is None:
        return 1, []

    plugins = marketplace.get("plugins", [])
    if not plugins:
        if verbose:
            print("No plugins found in marketplace.json")
        return 0, []

    # Track changes
    changes: list[tuple[str, str, str]] = []
    has_mismatch = False

    for plugin in plugins:
        plugin_name = plugin.get("name")
        if not plugin_name:
            continue

        # Check if plugin directory exists (it's a submodule)
        plugin_dir = repo_root / plugin_name
        if not plugin_dir.exists():
            if verbose:
                print(f"  {plugin_name}: directory not found (remote-only plugin)")
            continue

        # Get version from plugin's manifest (plugin.json, pyproject.toml, or package.json)
        plugin_version = get_plugin_version(plugin_dir)
        if plugin_version is None:
            if verbose:
                print(f"  {plugin_name}: no version found (checked plugin.json, pyproject.toml, package.json)")
            continue

        # Get current version in marketplace
        marketplace_version = plugin.get("version")

        # Check for mismatch
        if marketplace_version != plugin_version:
            has_mismatch = True
            changes.append((plugin_name, marketplace_version or "none", plugin_version))

            if verbose:
                print(f"  {plugin_name}: {marketplace_version or 'none'} -> {plugin_version}")

            if not check_only:
                plugin["version"] = plugin_version
        else:
            if verbose:
                print(f"  {plugin_name}: {plugin_version} (up to date)")

    # Save changes if not in check mode
    if changes and not check_only:
        if save_marketplace(marketplace_path, marketplace):
            print(f"Updated {len(changes)} plugin version(s) in marketplace.json")
        else:
            return 1, changes

    # Return appropriate exit code
    if check_only and has_mismatch:
        return 1, changes

    return 0, changes


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync plugin versions from submodules to marketplace.json"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for version mismatches without updating (exit 1 if mismatch)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Path to marketplace repository (default: current directory)",
    )

    args = parser.parse_args()

    if args.verbose:
        print(f"Syncing versions in: {args.repo_root}")

    exit_code, changes = sync_versions(
        args.repo_root,
        check_only=args.check,
        verbose=args.verbose,
    )

    if args.check:
        if changes:
            print(f"Version mismatch found for {len(changes)} plugin(s):")
            for name, old, new in changes:
                print(f"  {name}: marketplace has {old}, plugin has {new}")
            print("\nRun 'python scripts/sync-versions.py' to update marketplace.json")
        else:
            print("All plugin versions are in sync")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
