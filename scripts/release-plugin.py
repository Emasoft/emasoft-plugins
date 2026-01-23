#!/usr/bin/env python3
"""release-plugin.py - Comprehensive plugin release workflow with validations.

Usage:
    python scripts/release-plugin.py <plugin-name> <version> [--dry-run]

Example:
    python scripts/release-plugin.py perfect-skill-suggester 1.2.0
    python scripts/release-plugin.py claude-plugins-validation 1.2.0 --dry-run
"""

import json
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
    check: bool = False
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=120
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def validate_semver(version: str) -> bool:
    """Validate semver format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semver versions.

    Returns:
        -1 if v1 < v2
        0 if v1 == v2
        1 if v1 > v2
    """
    def parse(v: str) -> tuple[int, ...]:
        # Remove pre-release/build metadata for comparison
        base = v.split("-")[0].split("+")[0]
        return tuple(int(x) for x in base.split("."))

    p1, p2 = parse(v1), parse(v2)
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def find_plugins(repo_root: Path) -> dict[str, Path]:
    """Find all plugin directories and return as name -> path mapping."""
    plugins = {}
    for item in repo_root.iterdir():
        if item.is_dir():
            plugin_json = item / ".claude-plugin" / "plugin.json"
            if plugin_json.exists():
                plugins[item.name] = item
    return plugins


def get_current_version(plugin_json_path: Path) -> str:
    """Get current version from plugin.json."""
    with open(plugin_json_path) as f:
        data = json.load(f)
    return data.get("version", "0.0.0")


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
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("-")[0])
    return (
        f"{major}.{minor}.{patch + 1}",
        f"{major}.{minor + 1}.0",
        f"{major + 1}.0.0"
    )


def show_usage(repo_root: Path) -> None:
    """Show usage information."""
    print("Usage: python scripts/release-plugin.py <plugin-name> <version> [--dry-run]")
    print()
    print("Available plugins:")

    plugins = find_plugins(repo_root)
    for name, path in sorted(plugins.items()):
        plugin_json = path / ".claude-plugin" / "plugin.json"
        version = get_current_version(plugin_json) if plugin_json.exists() else "unknown"
        print(f"  - {name} (current: {version})")

    print()
    print("Options:")
    print("  --dry-run    Show what would be done without making changes")


def main() -> int:
    """Main release function."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Parse arguments
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    if len(args) < 1:
        show_usage(repo_root)
        return 1

    plugin_name = args[0]
    new_version = args[1] if len(args) > 1 else ""

    # Find plugin
    plugins = find_plugins(repo_root)
    if plugin_name not in plugins:
        log_error(f"Plugin not found: {plugin_name}")
        show_usage(repo_root)
        return 1

    plugin_dir = plugins[plugin_name]
    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"

    # Get current version
    current_version = get_current_version(plugin_json_path)

    print("=" * 60)
    print("Plugin Release Workflow")
    print("=" * 60)
    print(f"Plugin:          {plugin_name}")
    print(f"Current Version: {current_version}")
    print(f"New Version:     {new_version or '(auto-detect)'}")
    print(f"Dry Run:         {dry_run}")
    print("=" * 60)

    # If no version specified, suggest versions
    if not new_version:
        patch, minor, major = suggest_versions(current_version)
        print()
        print("No version specified. Suggested versions:")
        print(f"  Patch (bug fixes):     {patch}")
        print(f"  Minor (new features):  {minor}")
        print(f"  Major (breaking):      {major}")
        print()
        new_version = input(f"Enter new version (or press Enter for {patch}): ").strip()
        if not new_version:
            new_version = patch

    # Validate version format
    log_step("Validating version format...")
    if not validate_semver(new_version):
        log_error(f"Invalid semver format: {new_version}")
        print("Expected format: X.Y.Z (e.g., 1.2.3)")
        return 1
    log_success(f"Version format valid: {new_version}")

    # Check version increment
    log_step("Checking version increment...")
    cmp = compare_versions(new_version, current_version)
    if cmp <= 0:
        log_error(f"New version ({new_version}) must be greater than current version ({current_version})")
        return 1
    log_success(f"Version increment valid: {current_version} → {new_version}")

    # Check for uncommitted changes
    log_step("Checking for uncommitted changes in plugin...")
    is_clean, changes = check_git_status(plugin_dir)
    if not is_clean:
        log_warning(f"Uncommitted changes detected in {plugin_name}:")
        print(changes)
        if not dry_run:
            confirm = input("Continue anyway? (y/N): ")
            if confirm.lower() != "y":
                log_error("Aborted by user")
                return 1
    else:
        log_success("Working directory clean")

    # Check if tag already exists
    log_step(f"Checking if tag v{new_version} already exists...")
    if check_git_tag_exists(f"v{new_version}", plugin_dir):
        log_error(f"Tag v{new_version} already exists in {plugin_name}")
        return 1
    log_success(f"Tag v{new_version} is available")

    # Run plugin validation
    log_step("Running plugin validation...")
    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_plugin.py"
    if validator.exists():
        code, stdout, stderr = run_command(
            ["uv", "run", "python", str(validator), str(plugin_dir)],
            cwd=repo_root / "claude-plugins-validation"
        )
        if code == 0:
            log_success("Plugin validation passed")
        else:
            log_error("Plugin validation failed")
            print(stdout + stderr)
            if not dry_run:
                confirm = input("Continue despite validation errors? (y/N): ")
                if confirm.lower() != "y":
                    return 1
    else:
        log_warning("Validation script not found, skipping validation")

    # Run skill validation if skills exist
    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        log_step("Running skill validation...")
        skill_validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_skill.py"
        if skill_validator.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill_name = skill_dir.name
                    code, _, _ = run_command(
                        ["uv", "run", "python", str(skill_validator), str(skill_dir)],
                        cwd=repo_root / "claude-plugins-validation"
                    )
                    if code == 0:
                        log_success(f"Skill '{skill_name}' validation passed")
                    else:
                        log_warning(f"Skill '{skill_name}' validation has issues")

    # Run hook validation if hooks exist
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        log_step("Running hook validation...")
        hook_validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_hook.py"
        if hook_validator.exists():
            code, _, _ = run_command(
                ["uv", "run", "python", str(hook_validator), str(hooks_json)],
                cwd=repo_root / "claude-plugins-validation"
            )
            if code == 0:
                log_success("Hook validation passed")
            else:
                log_warning("Hook validation has issues")

    # Lint Python scripts
    scripts_dir = plugin_dir / "scripts"
    py_scripts = list(scripts_dir.glob("*.py")) if scripts_dir.exists() else []
    if py_scripts:
        log_step("Linting Python scripts...")
        code, stdout, stderr = run_command(
            ["uv", "run", "ruff", "check"] + [str(f) for f in py_scripts],
            cwd=plugin_dir
        )
        if code == 0:
            log_success("Python linting passed")
        else:
            log_warning("Python linting has issues")
            if not dry_run:
                confirm = input("Continue despite linting errors? (y/N): ")
                if confirm.lower() != "y":
                    return 1

    # Lint Bash scripts
    sh_scripts = list(scripts_dir.glob("*.sh")) if scripts_dir.exists() else []
    if sh_scripts:
        log_step("Linting Bash scripts...")
        code, _, _ = run_command(["which", "shellcheck"])
        if code == 0:
            code, _, _ = run_command(["shellcheck"] + [str(f) for f in sh_scripts])
            if code == 0:
                log_success("Bash linting passed")
            else:
                log_warning("Bash linting has issues")

    if dry_run:
        print()
        print("=" * 60)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 60)
        print()
        print("The following actions would be performed:")
        print(f"  1. Update {plugin_name}/plugin.json version to {new_version}")
        print(f"  2. Commit changes in {plugin_name} submodule")
        print(f"  3. Create tag v{new_version} in {plugin_name}")
        print("  4. Sync version to marketplace.json")
        print("  5. Commit and tag marketplace")
        print()
        return 0

    # === MAKE CHANGES ===

    log_step("Updating plugin.json version...")
    update_plugin_version(plugin_json_path, new_version)
    log_success(f"Updated version to {new_version}")

    log_step("Committing changes in plugin submodule...")
    run_command(["git", "add", "-A"], cwd=plugin_dir)
    code, _, _ = run_command(
        ["git", "commit", "-m", f"feat({plugin_name}): bump version to {new_version}"],
        cwd=plugin_dir
    )
    if code != 0:
        log_warning("Nothing to commit in submodule")

    # Commit CHANGELOG if updated
    changelog = plugin_dir / "CHANGELOG.md"
    if changelog.exists():
        is_clean, _ = check_git_status(plugin_dir)
        if not is_clean:
            run_command(["git", "add", "CHANGELOG.md"], cwd=plugin_dir)
            run_command(["git", "commit", "--amend", "--no-edit"], cwd=plugin_dir)

    log_step(f"Creating tag v{new_version} in plugin...")
    run_command(
        ["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version}"],
        cwd=plugin_dir
    )
    log_success(f"Created tag v{new_version}")

    log_step("Syncing version to marketplace.json...")
    sync_script = repo_root / "scripts" / "sync-versions.py"
    if sync_script.exists():
        run_command(["python3", str(sync_script), "--verbose", str(repo_root)], cwd=repo_root)
        log_success("Marketplace.json updated")

    log_step("Committing marketplace changes...")
    run_command(["git", "add", "-A"], cwd=repo_root)
    code, _, _ = run_command(
        ["git", "commit", "-m", f"feat: release {plugin_name} v{new_version}"],
        cwd=repo_root
    )
    if code != 0:
        log_warning("Nothing to commit in marketplace")

    # Commit CHANGELOG if updated
    marketplace_changelog = repo_root / "CHANGELOG.md"
    if marketplace_changelog.exists():
        is_clean, _ = check_git_status(repo_root)
        if not is_clean:
            run_command(["git", "add", "CHANGELOG.md"], cwd=repo_root)
            run_command(["git", "commit", "--amend", "--no-edit"], cwd=repo_root)

    # Create marketplace tag
    tag_name = f"{plugin_name}-v{new_version}"
    log_step(f"Tagging marketplace ({tag_name})...")
    if check_git_tag_exists(tag_name, repo_root):
        run_command(["git", "tag", "-d", tag_name], cwd=repo_root)
    run_command(
        ["git", "tag", "-a", tag_name, "-m", f"Release {plugin_name} v{new_version}"],
        cwd=repo_root
    )
    log_success(f"Created marketplace tag: {tag_name}")

    print()
    print("=" * 60)
    print(f"{GREEN}RELEASE COMPLETE{NC}")
    print("=" * 60)
    print()
    print(f"Plugin:     {plugin_name}")
    print(f"Version:    {new_version}")
    print(f"Plugin Tag: v{new_version}")
    print(f"Marketplace Tag: {tag_name}")
    print()
    print("Next steps:")
    print(f"  1. Push plugin submodule:    cd {plugin_name} && git push && git push --tags")
    print("  2. Push marketplace:         git push && git push --tags")
    print(f"  3. Reinstall in Claude Code: claude plugin uninstall {plugin_name}@emasoft-plugins && claude plugin install {plugin_name}@emasoft-plugins")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
