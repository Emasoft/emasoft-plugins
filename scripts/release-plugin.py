#!/usr/bin/env python3
"""release-plugin.py - Comprehensive plugin release workflow with validations.

Usage:
    python scripts/release-plugin.py [plugin-name ...] [options]

If no plugin names are specified, all plugins in the marketplace are released.
When releasing multiple plugins, each gets an auto-incremented patch version.

Examples:
    # Release one plugin with explicit version
    python scripts/release-plugin.py perfect-skill-suggester --version 1.2.0

    # Release two plugins, auto-patch, non-interactive
    python scripts/release-plugin.py perfect-skill-suggester claude-plugins-validation -y

    # Dry-run release all plugins
    python scripts/release-plugin.py --yes --dry-run

    # Strict mode: fail on any validation warning
    python scripts/release-plugin.py perfect-skill-suggester -y --strict

    # Backward-compatible: positional version (single plugin only)
    python scripts/release-plugin.py perfect-skill-suggester 2.0.0 -y

Options:
    --version X.Y.Z  Explicit version (only valid for single plugin)
    --dry-run        Show what would be done without making changes
    --yes, -y        Non-interactive mode (auto-confirm all prompts, auto-patch)
    --strict         Fail on any validation warning or linting issue
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ANSI Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def log_step(message: str) -> None:
    """Print a step header."""
    print(f"\n{BLUE}▶ {message}{NC}")


def log_success(message: str) -> None:
    """Print success message."""
    print(f"{GREEN}✔ {message}{NC}")


def log_warning(message: str) -> None:
    """Print warning message."""
    print(f"{YELLOW}⚠ {message}{NC}")


def log_error(message: str) -> None:
    """Print error message."""
    print(f"{RED}✘ {message}{NC}")


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = False,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=capture, text=True, timeout=120
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def validate_semver(version: str) -> bool:
    """Validate semver format (X.Y.Z with optional pre-release/build)."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semver versions. Returns -1 if v1<v2, 0 if equal, 1 if v1>v2."""

    def parse(v: str) -> tuple[int, ...]:
        base = v.split("-")[0].split("+")[0]
        return tuple(int(x) for x in base.split("."))

    p1, p2 = parse(v1), parse(v2)
    if p1 < p2:
        return -1
    if p1 > p2:
        return 1
    return 0


def find_plugins(repo_root: Path) -> dict[str, Path]:
    """Find all plugin directories in OUTPUT_SKILLS/.

    A plugin directory is any subdirectory containing .claude-plugin/plugin.json.
    Returns a dict mapping plugin name to its directory path.
    """
    plugins = {}
    output_skills = repo_root / "OUTPUT_SKILLS"
    if not output_skills.is_dir():
        return plugins
    for item in output_skills.iterdir():
        if item.is_dir():
            plugin_json = item / ".claude-plugin" / "plugin.json"
            if plugin_json.exists():
                plugins[item.name] = item
    return plugins


def get_current_version(plugin_json_path: Path) -> str:
    """Get current version from plugin.json."""
    with open(plugin_json_path) as f:
        data: dict[str, object] = json.load(f)
    version = data.get("version", "0.0.0")
    if not isinstance(version, str):
        return "0.0.0"
    return version


def update_plugin_version(plugin_json_path: Path, new_version: str) -> None:
    """Update version in plugin.json."""
    with open(plugin_json_path) as f:
        data = json.load(f)
    data["version"] = new_version
    with open(plugin_json_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def check_git_status(path: Path) -> tuple[bool, str]:
    """Check if directory has uncommitted changes."""
    code, stdout, _ = run_command(["git", "status", "--porcelain"], cwd=path)
    is_clean = code == 0 and stdout.strip() == ""
    return is_clean, stdout.strip()


def check_git_tag_exists(tag: str, path: Path) -> bool:
    """Check if a git tag exists."""
    code, stdout, _ = run_command(["git", "tag", "-l", tag], cwd=path)
    return code == 0 and tag in stdout


def suggest_versions(current: str) -> tuple[str, str, str]:
    """Suggest next patch, minor, and major versions."""
    parts = current.split(".")
    major, minor, patch = (
        int(parts[0]),
        int(parts[1]),
        int(parts[2].split("-")[0]),
    )
    return (
        f"{major}.{minor}.{patch + 1}",
        f"{major}.{minor + 1}.0",
        f"{major + 1}.0.0",
    )


def find_universal_validator(repo_root: Path) -> Path | None:
    """Find the claude-plugins-validation universal validator script."""
    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_plugin.py"
    return validator if validator.exists() else None


def find_universal_validator_cwd(repo_root: Path) -> Path | None:
    """Find the working directory for running the universal validator."""
    cpv_dir = repo_root / "claude-plugins-validation"
    return cpv_dir if (cpv_dir / "scripts" / "validate_plugin.py").exists() else None


def dereference_symlinks(plugin_dir: Path) -> dict[Path, Path]:
    """Replace symlinks with real file copies for git commit (publishing).

    When publishing plugins to GitHub, symlinks must be dereferenced because
    each plugin repo must be self-contained. This copies the real files in
    place of symlinks, returning a map to restore them after commit.
    """
    symlink_map: dict[Path, Path] = {}
    scripts_dir = plugin_dir / "scripts"
    if not scripts_dir.exists():
        return symlink_map
    for f in scripts_dir.iterdir():
        if f.is_symlink():
            target = f.resolve()
            symlink_map[f] = target
            f.unlink()
            shutil.copy2(target, f)
    return symlink_map


def restore_symlinks(symlink_map: dict[Path, Path]) -> None:
    """Restore symlinks after publishing commit."""
    for link_path, target in symlink_map.items():
        if link_path.exists():
            link_path.unlink()
        # Compute relative path from link's parent to target
        try:
            rel_target = target.relative_to(link_path.parent)
        except ValueError:
            rel_target = Path(os.path.relpath(target, link_path.parent))
        link_path.symlink_to(rel_target)


def show_usage(repo_root: Path) -> None:
    """Show usage information."""
    print("Usage: python scripts/release-plugin.py [plugin-name ...] [options]")
    print()
    print("If no plugin names given, all plugins are released.")
    print()
    print("Available plugins:")

    plugins = find_plugins(repo_root)
    for name, path in sorted(plugins.items()):
        plugin_json = path / ".claude-plugin" / "plugin.json"
        version = (
            get_current_version(plugin_json) if plugin_json.exists() else "unknown"
        )
        print(f"  - {name} (current: {version})")

    print()
    print("Options:")
    print("  --version X.Y.Z  Explicit version (single plugin only)")
    print("  --dry-run        Show what would be done without making changes")
    print(
        "  --yes, -y        Non-interactive mode "
        "(auto-confirm, default to patch version)"
    )
    print("  --strict         Fail on any validation warning or linting issue")


def prompt_or_auto(
    message: str,
    auto_yes: bool,
    dry_run: bool,
    strict: bool,
    strict_reason: str,
) -> bool:
    """Ask for confirmation or auto-decide based on flags.

    Returns True if execution should continue, False if it should stop.
    """
    if strict:
        log_error(f"Strict mode: {strict_reason}")
        return False
    if auto_yes:
        log_warning(f"Auto-continuing (-y flag): {strict_reason}")
        return True
    if dry_run:
        return True
    confirm = input(message)
    return confirm.lower() == "y"


def release_single_plugin(
    plugin_name: str,
    plugin_dir: Path,
    new_version: str,
    repo_root: Path,
    dry_run: bool,
    auto_yes: bool,
    strict: bool,
) -> tuple[bool, str]:
    """Release a single plugin.

    Runs all validations, bumps version, commits and tags in the plugin
    submodule. Does NOT touch the marketplace repo (that happens in main).

    Args:
        plugin_name: Name of the plugin directory.
        plugin_dir: Path to the plugin directory.
        new_version: Explicit version string, or "" for auto-patch.
        repo_root: Path to the marketplace repo root.
        dry_run: If True, do not make any changes.
        auto_yes: If True, skip all interactive prompts.
        strict: If True, fail on any validation warning.

    Returns:
        (success, final_version) tuple.
    """
    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    current_version = get_current_version(plugin_json_path)

    print()
    print("=" * 60)
    print(f"Releasing: {plugin_name}")
    print("=" * 60)
    print(f"  Current Version: {current_version}")
    print(f"  New Version:     {new_version or '(auto-patch)'}")
    print("=" * 60)

    # --- Determine version ---
    if not new_version:
        patch, minor, major = suggest_versions(current_version)
        if auto_yes:
            new_version = patch
            log_success(f"Auto-selected patch version: {new_version}")
        else:
            print()
            print("No version specified. Suggested versions:")
            print(f"  Patch (bug fixes):     {patch}")
            print(f"  Minor (new features):  {minor}")
            print(f"  Major (breaking):      {major}")
            print()
            new_version = input(
                f"Enter new version (or press Enter for {patch}): "
            ).strip()
            if not new_version:
                new_version = patch

    # --- Validate version format ---
    log_step("Validating version format...")
    if not validate_semver(new_version):
        log_error(f"Invalid semver format: {new_version}")
        print("Expected format: X.Y.Z (e.g., 1.2.3)")
        return False, ""
    log_success(f"Version format valid: {new_version}")

    # --- Check version increment ---
    log_step("Checking version increment...")
    cmp = compare_versions(new_version, current_version)
    if cmp <= 0:
        log_error(
            f"New version ({new_version}) must be greater than "
            f"current version ({current_version})"
        )
        return False, ""
    log_success(f"Version increment valid: {current_version} -> {new_version}")

    # --- Check for uncommitted changes ---
    log_step("Checking for uncommitted changes in plugin...")
    is_clean, changes = check_git_status(plugin_dir)
    if not is_clean:
        log_warning(f"Uncommitted changes detected in {plugin_name}:")
        print(changes)
        if not prompt_or_auto(
            "Continue anyway? (y/N): ",
            auto_yes,
            dry_run,
            strict,
            "uncommitted changes are not allowed",
        ):
            return False, ""
    else:
        log_success("Working directory clean")

    # --- Check if tag already exists ---
    log_step(f"Checking if tag v{new_version} already exists...")
    if check_git_tag_exists(f"v{new_version}", plugin_dir):
        log_error(f"Tag v{new_version} already exists in {plugin_name}")
        return False, ""
    log_success(f"Tag v{new_version} is available")

    # --- Run universal validator from claude-plugins-validation ---
    log_step("Running universal plugin validation (claude-plugins-validation)...")
    validator = find_universal_validator(repo_root)
    validator_cwd = find_universal_validator_cwd(repo_root)
    if validator and validator_cwd:
        log_success(f"Using validator: {validator}")
        code, stdout, stderr = run_command(
            ["uv", "run", "python", str(validator), str(plugin_dir)],
            cwd=validator_cwd,
        )
        if code == 0:
            log_success("Universal plugin validation passed")
        else:
            log_error("Universal plugin validation failed")
            print(stdout + stderr)
            if not prompt_or_auto(
                "Continue despite validation errors? (y/N): ",
                auto_yes,
                dry_run,
                strict,
                "validation errors found",
            ):
                return False, ""
    else:
        log_warning(
            "Universal validator not found "
            "(claude-plugins-validation/scripts/validate_plugin.py)"
        )

    # --- Dry run stops here ---
    if dry_run:
        print()
        print(f"  DRY RUN for {plugin_name}: would release v{new_version}")
        return True, new_version

    # === MAKE CHANGES ===

    log_step("Updating plugin.json version...")
    update_plugin_version(plugin_json_path, new_version)
    log_success(f"Updated version to {new_version}")

    # Dereference symlinks for publishing (GitHub needs real files, not symlinks)
    symlink_map = dereference_symlinks(plugin_dir)
    if symlink_map:
        log_success(f"Dereferenced {len(symlink_map)} symlinks for publishing")

    log_step("Committing changes in plugin submodule...")
    run_command(["git", "add", "-A"], cwd=plugin_dir)
    code, _, _ = run_command(
        [
            "git",
            "commit",
            "-m",
            f"feat({plugin_name}): bump version to {new_version}",
        ],
        cwd=plugin_dir,
    )
    if code != 0:
        log_warning("Nothing to commit in submodule")

    # Amend CHANGELOG into commit if it was updated
    changelog = plugin_dir / "CHANGELOG.md"
    if changelog.exists():
        is_clean, _ = check_git_status(plugin_dir)
        if not is_clean:
            run_command(["git", "add", "CHANGELOG.md"], cwd=plugin_dir)
            run_command(["git", "commit", "--amend", "--no-edit"], cwd=plugin_dir)

    log_step(f"Creating tag v{new_version} in plugin...")
    run_command(
        [
            "git",
            "tag",
            "-a",
            f"v{new_version}",
            "-m",
            f"Release v{new_version}",
        ],
        cwd=plugin_dir,
    )
    log_success(f"Created tag v{new_version}")

    # Restore symlinks after commit+tag
    if symlink_map:
        restore_symlinks(symlink_map)
        log_success(f"Restored {len(symlink_map)} symlinks")

    return True, new_version


def main() -> int:
    """Main entry point: parse args, release plugins, update marketplace."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # --- Parse flags ---
    raw_args = sys.argv[1:]
    dry_run = "--dry-run" in raw_args
    auto_yes = "--yes" in raw_args or "-y" in raw_args
    strict = "--strict" in raw_args

    # Extract --version value (supports --version X.Y.Z and --version=X.Y.Z)
    explicit_version = ""
    positional_args: list[str] = []
    skip_next = False
    for i, arg in enumerate(raw_args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--version" and i + 1 < len(raw_args):
            explicit_version = raw_args[i + 1]
            skip_next = True
            continue
        if arg.startswith("--version="):
            explicit_version = arg.split("=", 1)[1]
            continue
        if arg in ("--dry-run", "--yes", "-y", "--strict"):
            continue
        positional_args.append(arg)

    # --- Determine plugin list ---
    all_plugins = find_plugins(repo_root)
    plugin_names: list[str] = []

    # Backward compatibility: release-plugin.py <name> <version>
    # If second positional arg looks like a semver, treat it as the version
    if len(positional_args) >= 2 and validate_semver(positional_args[1]):
        plugin_names = [positional_args[0]]
        if not explicit_version:
            explicit_version = positional_args[1]
    elif positional_args:
        plugin_names = positional_args

    # If no plugins specified, release all
    if not plugin_names:
        plugin_names = sorted(all_plugins.keys())
        if not plugin_names:
            log_error("No plugins found in marketplace")
            return 1
        print(f"No plugins specified. Will release ALL {len(plugin_names)} plugins:")
        for name in plugin_names:
            pjp = all_plugins[name] / ".claude-plugin" / "plugin.json"
            ver = get_current_version(pjp) if pjp.exists() else "?"
            print(f"  - {name} ({ver})")
        print()
        if not auto_yes:
            confirm = input("Proceed with releasing all plugins? (y/N): ")
            if confirm.lower() != "y":
                log_error("Aborted by user")
                return 1

    # Validate all plugin names exist
    for name in plugin_names:
        if name not in all_plugins:
            log_error(f"Plugin not found: {name}")
            show_usage(repo_root)
            return 1

    # --version is only valid with a single plugin
    if explicit_version and len(plugin_names) > 1:
        log_error("--version can only be used when releasing a single plugin")
        return 1

    # --- Print header ---
    print()
    print("=" * 60)
    print("Plugin Release Workflow")
    print("=" * 60)
    print(f"  Plugins:       {', '.join(plugin_names)}")
    print(f"  Version:       {explicit_version or '(auto-patch each)'}")
    print(f"  Dry Run:       {dry_run}")
    print(f"  Auto-confirm:  {auto_yes}")
    print(f"  Strict:        {strict}")
    print("=" * 60)

    # --- Release each plugin ---
    results: list[tuple[str, bool, str]] = []
    for name in plugin_names:
        version_for_plugin = explicit_version if len(plugin_names) == 1 else ""
        success, final_version = release_single_plugin(
            plugin_name=name,
            plugin_dir=all_plugins[name],
            new_version=version_for_plugin,
            repo_root=repo_root,
            dry_run=dry_run,
            auto_yes=auto_yes,
            strict=strict,
        )
        results.append((name, success, final_version))
        if not success and strict:
            log_error(f"Strict mode: stopping after {name} failure")
            break

    # Partition results
    succeeded = [(n, v) for n, s, v in results if s]
    failed = [n for n, s, _ in results if not s]

    if not succeeded:
        log_error("No plugins were released successfully")
        return 1

    # --- Dry run summary ---
    if dry_run:
        print()
        print("=" * 60)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 60)
        for name, version in succeeded:
            print(f"  Would release: {name} v{version}")
        if failed:
            print(f"  Would skip (failed validation): {', '.join(failed)}")
        return 0

    # --- Sync marketplace.json (once for all plugins) ---
    log_step("Syncing versions to marketplace.json...")
    sync_script = repo_root / "scripts" / "sync-versions.py"
    if sync_script.exists():
        run_command(
            ["python3", str(sync_script), "--verbose", str(repo_root)],
            cwd=repo_root,
        )
        log_success("Marketplace.json updated")

    # --- Validate marketplace structure ---
    log_step("Validating marketplace structure...")
    marketplace_validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_marketplace.py"
    if marketplace_validator.exists():
        marketplace_cwd = repo_root / "claude-plugins-validation"
        code, stdout, stderr = run_command(
            ["uv", "run", "python", str(marketplace_validator), str(repo_root)],
            cwd=marketplace_cwd,
        )
        if code == 0:
            log_success("Marketplace validation passed")
        else:
            log_warning("Marketplace validation has issues")
            print(stdout + stderr)
    else:
        log_warning("Marketplace validator not found")

    # --- Commit marketplace (single commit for all plugins) ---
    released_list = ", ".join(f"{n} v{v}" for n, v in succeeded)
    commit_msg = f"feat: release {released_list}"

    log_step("Committing marketplace changes...")
    run_command(["git", "add", "-A"], cwd=repo_root)
    code, _, _ = run_command(
        ["git", "commit", "-m", commit_msg],
        cwd=repo_root,
    )
    if code != 0:
        log_warning("Nothing to commit in marketplace")

    # Amend CHANGELOG if updated
    marketplace_changelog = repo_root / "CHANGELOG.md"
    if marketplace_changelog.exists():
        is_clean, _ = check_git_status(repo_root)
        if not is_clean:
            run_command(["git", "add", "CHANGELOG.md"], cwd=repo_root)
            run_command(["git", "commit", "--amend", "--no-edit"], cwd=repo_root)

    # --- Create marketplace tags (one per released plugin) ---
    for name, version in succeeded:
        tag_name = f"{name}-v{version}"
        log_step(f"Tagging marketplace ({tag_name})...")
        if check_git_tag_exists(tag_name, repo_root):
            run_command(["git", "tag", "-d", tag_name], cwd=repo_root)
        run_command(
            [
                "git",
                "tag",
                "-a",
                tag_name,
                "-m",
                f"Release {name} v{version}",
            ],
            cwd=repo_root,
        )
        log_success(f"Created marketplace tag: {tag_name}")

    # --- Print summary ---
    print()
    print("=" * 60)
    print(f"{GREEN}RELEASE COMPLETE{NC}")
    print("=" * 60)
    print()
    for name, version in succeeded:
        print(f"  {GREEN}✔{NC} {name} v{version}")
    for name in failed:
        print(f"  {RED}✘{NC} {name} (failed)")
    print()
    print("Next steps:")
    for name, _ in succeeded:
        print(f"  Push {name}: cd {name} && git push && git push --tags")
    print("  Push marketplace: git push && git push --tags")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
