#!/usr/bin/env python3
"""verify-release.py - Pre-release verification for marketplace and all plugins.

Usage:
    python scripts/verify-release.py [--fix]

Options:
    --fix    Attempt to fix issues automatically where possible
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


class VerificationResult:
    """Track verification results."""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def check_pass(self, message: str) -> None:
        """Record a passed check."""
        print(f"  {GREEN}✔{NC} {message}")
        self.total += 1
        self.passed += 1

    def check_fail(self, message: str) -> None:
        """Record a failed check."""
        print(f"  {RED}✘{NC} {message}")
        self.total += 1
        self.failed += 1

    def check_warn(self, message: str) -> None:
        """Record a warning."""
        print(f"  {YELLOW}⚠{NC} {message}")
        self.total += 1
        self.warnings += 1


def section(title: str) -> None:
    """Print a section header."""
    print()
    print(f"{BLUE}━━━ {title} ━━━{NC}")


def run_command(cmd: list[str], cwd: Path | None = None, capture: bool = True) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def check_git_status(path: Path) -> bool:
    """Check if directory has uncommitted changes."""
    code, stdout, _ = run_command(["git", "status", "--porcelain"], cwd=path)
    return code == 0 and stdout.strip() == ""


def check_git_tag_exists(tag: str, path: Path) -> bool:
    """Check if a git tag exists."""
    code, stdout, _ = run_command(["git", "tag", "-l", tag], cwd=path)
    return code == 0 and tag in stdout


def validate_semver(version: str) -> bool:
    """Validate semver format."""
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def find_plugins(repo_root: Path) -> list[Path]:
    """Find all plugin directories."""
    plugins = []
    for item in repo_root.iterdir():
        if item.is_dir():
            plugin_json = item / ".claude-plugin" / "plugin.json"
            if plugin_json.exists():
                plugins.append(item)
    return plugins


def verify_repository_state(repo_root: Path, results: VerificationResult) -> None:
    """Verify repository state."""
    section("1. Repository State")

    # Check main repo
    if check_git_status(repo_root):
        results.check_pass("Main repo is clean")
    else:
        results.check_warn("Main repo has uncommitted changes")

    # Check submodules
    for submodule in ["perfect-skill-suggester", "claude-plugins-validation"]:
        submodule_path = repo_root / submodule
        if submodule_path.exists():
            if check_git_status(submodule_path):
                results.check_pass(f"Submodule '{submodule}' is clean")
            else:
                results.check_warn(f"Submodule '{submodule}' has uncommitted changes")


def verify_version_consistency(repo_root: Path, results: VerificationResult, fix_mode: bool) -> None:
    """Verify version consistency between plugins and marketplace."""
    section("2. Version Consistency")

    sync_script = repo_root / "scripts" / "sync-versions.py"
    if sync_script.exists():
        code, _, _ = run_command(
            ["python3", str(sync_script), "--check", str(repo_root)],
            cwd=repo_root
        )
        if code == 0:
            results.check_pass("Plugin versions match marketplace.json")
        else:
            if fix_mode:
                run_command(["python3", str(sync_script), str(repo_root)], cwd=repo_root)
                results.check_warn("Plugin versions synced to marketplace.json (fixed)")
            else:
                results.check_fail("Plugin versions don't match marketplace.json (run with --fix)")

    # Check each plugin has valid version
    for plugin_dir in find_plugins(repo_root):
        plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
        try:
            with open(plugin_json_path) as f:
                data = json.load(f)
            name = data.get("name", plugin_dir.name)
            version = data.get("version", "")
            if version and validate_semver(version):
                results.check_pass(f"Plugin '{name}' has valid version: {version}")
            else:
                results.check_fail(f"Plugin '{name}' has invalid or missing version")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            results.check_fail(f"Plugin '{plugin_dir.name}' has invalid plugin.json: {e}")


def verify_marketplace_validation(repo_root: Path, results: VerificationResult) -> None:
    """Run marketplace validation."""
    section("3. Marketplace Validation")

    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_marketplace.py"
    if validator.exists():
        code, stdout, _ = run_command(
            ["uv", "run", "python", str(validator), str(repo_root)],
            cwd=repo_root / "claude-plugins-validation"
        )
        if "PASSED" in stdout or code == 0:
            results.check_pass("Marketplace validation passed")
        else:
            results.check_fail("Marketplace validation failed")
            print(f"    Run: uv run python {validator} . --verbose")
    else:
        results.check_warn("Marketplace validator not found")


def verify_plugin_validations(repo_root: Path, results: VerificationResult) -> None:
    """Validate each plugin."""
    section("4. Plugin Validations")

    validator = repo_root / "claude-plugins-validation" / "scripts" / "validate_plugin.py"

    for plugin_dir in find_plugins(repo_root):
        plugin_name = plugin_dir.name
        if validator.exists():
            code, stdout, stderr = run_command(
                ["uv", "run", "python", str(validator), str(plugin_dir)],
                cwd=repo_root / "claude-plugins-validation"
            )
            output = stdout + stderr
            if "All checks passed" in output or code == 0:
                results.check_pass(f"Plugin '{plugin_name}' validation passed")
            elif "MINOR" in output:
                results.check_warn(f"Plugin '{plugin_name}' has minor issues")
            else:
                results.check_fail(f"Plugin '{plugin_name}' validation failed")
                print(f"    Run: uv run python {validator} {plugin_dir} --verbose")
        else:
            results.check_warn(f"Plugin validator not found for '{plugin_name}'")


def verify_required_files(repo_root: Path, results: VerificationResult) -> None:
    """Check for required files."""
    section("5. Required Files")

    # Marketplace files
    for file in ["README.md", "LICENSE", ".claude-plugin/marketplace.json"]:
        if (repo_root / file).exists():
            results.check_pass(f"Marketplace has {file}")
        else:
            results.check_fail(f"Marketplace missing {file}")

    # Plugin files
    for plugin_dir in find_plugins(repo_root):
        plugin_name = plugin_dir.name
        for file in ["README.md", "LICENSE"]:
            if (plugin_dir / file).exists():
                results.check_pass(f"Plugin '{plugin_name}' has {file}")
            else:
                results.check_warn(f"Plugin '{plugin_name}' missing {file}")


def verify_git_tags(repo_root: Path, results: VerificationResult) -> None:
    """Check if plugins have tags matching their versions."""
    section("6. Git Tags")

    for plugin_dir in find_plugins(repo_root):
        plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
        try:
            with open(plugin_json_path) as f:
                data = json.load(f)
            plugin_name = data.get("name", plugin_dir.name)
            version = data.get("version", "")
            tag = f"v{version}"

            if check_git_tag_exists(tag, plugin_dir):
                results.check_pass(f"Plugin '{plugin_name}' has tag {tag}")
            else:
                results.check_warn(f"Plugin '{plugin_name}' missing tag {tag}")
        except (json.JSONDecodeError, FileNotFoundError):
            pass


def verify_script_linting(repo_root: Path, results: VerificationResult, fix_mode: bool) -> None:
    """Lint Python and Bash scripts."""
    section("7. Script Linting")

    # Find Python files (excluding venv)
    py_files = []
    for py_file in repo_root.rglob("*.py"):
        if ".venv" not in str(py_file):
            py_files.append(str(py_file))

    if py_files:
        py_files_str = py_files[:20]  # Limit to 20 files
        code, _, _ = run_command(["uv", "run", "ruff", "check"] + py_files_str, cwd=repo_root)
        if code == 0:
            results.check_pass("Python scripts pass linting")
        else:
            if fix_mode:
                run_command(["uv", "run", "ruff", "check", "--fix"] + py_files_str, cwd=repo_root)
                results.check_warn("Python scripts had issues (attempted fix)")
            else:
                results.check_warn("Python scripts have linting issues")

    # Check shellcheck for bash scripts
    sh_files = list(repo_root.rglob("*.sh"))
    if sh_files:
        code, _, _ = run_command(["which", "shellcheck"])
        if code == 0:
            sh_files_str = [str(f) for f in sh_files[:20] if ".venv" not in str(f)]
            code, _, _ = run_command(["shellcheck"] + sh_files_str)
            if code == 0:
                results.check_pass("Bash scripts pass shellcheck")
            else:
                results.check_warn("Bash scripts have shellcheck warnings")


def verify_json_validity(repo_root: Path, results: VerificationResult) -> None:
    """Check all JSON files are valid."""
    section("8. JSON Validity")

    invalid_files = []
    for json_file in repo_root.rglob("*.json"):
        if ".venv" in str(json_file) or "node_modules" in str(json_file):
            continue
        try:
            with open(json_file) as f:
                json.load(f)
        except json.JSONDecodeError:
            invalid_files.append(json_file)
            results.check_fail(f"Invalid JSON: {json_file}")

    if not invalid_files:
        results.check_pass("All JSON files are valid")


def main() -> int:
    """Main verification function."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    fix_mode = "--fix" in sys.argv

    print("=" * 60)
    print("Pre-Release Verification")
    print("=" * 60)
    print(f"Repository: {repo_root}")
    print(f"Fix Mode:   {fix_mode}")
    print("=" * 60)

    results = VerificationResult()

    # Run all verifications
    verify_repository_state(repo_root, results)
    verify_version_consistency(repo_root, results, fix_mode)
    verify_marketplace_validation(repo_root, results)
    verify_plugin_validations(repo_root, results)
    verify_required_files(repo_root, results)
    verify_git_tags(repo_root, results)
    verify_script_linting(repo_root, results, fix_mode)
    verify_json_validity(repo_root, results)

    # Summary
    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total Checks:   {results.total}")
    print(f"Passed:         {GREEN}{results.passed}{NC}")
    print(f"Warnings:       {YELLOW}{results.warnings}{NC}")
    print(f"Failed:         {RED}{results.failed}{NC}")
    print("=" * 60)

    if results.failed > 0:
        print(f"{RED}VERIFICATION FAILED{NC}")
        print("Please fix the failed checks before releasing.")
        return 1
    elif results.warnings > 0:
        print(f"{YELLOW}VERIFICATION PASSED WITH WARNINGS{NC}")
        print("Consider addressing warnings before releasing.")
        return 0
    else:
        print(f"{GREEN}VERIFICATION PASSED{NC}")
        print("Ready for release!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
