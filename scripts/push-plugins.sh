#!/usr/bin/env bash
# Validate plugins from GitHub and push marketplace.
# Usage: ./scripts/push-plugins.sh [plugin-name ...] [--dry-run] [--no-validate]
#
# Plugins live in their own GitHub repos. This script:
#   1. Clones each plugin from GitHub (shallow) to a temp dir
#   2. Validates with CPV validate_plugin.py --strict (zero tolerance)
#   3. Validates marketplace.json with validate_marketplace.py --strict
#   4. Syncs marketplace.json versions from GitHub plugin.json files
#   5. Pushes the marketplace repo
#
# Individual plugin repos are pushed independently from their own clones.
# This script only validates them and pushes the marketplace.
#
# Examples:
#   ./scripts/push-plugins.sh                     # Validate all + push marketplace
#   ./scripts/push-plugins.sh --dry-run            # Validate all, don't push
#   ./scripts/push-plugins.sh claude-plugins-validation  # Validate one + push marketplace
#   ./scripts/push-plugins.sh --no-validate        # Skip validation (NOT recommended)

set -euo pipefail

# Derive paths from the script's own location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find the CPV validator from the plugin cache (latest installed version)
find_cpv_dir() {
    local cache_base="$HOME/.claude/plugins/cache/emasoft-plugins/claude-plugins-validation"
    if [ ! -d "$cache_base" ]; then
        echo ""
        return
    fi
    # Find latest version directory (sort by version number)
    local latest
    latest=$(ls -1d "$cache_base"/*/ 2>/dev/null | sort -t/ -k"$(echo "$cache_base" | tr -cd '/' | wc -c | tr -d ' ')" -V | tail -1)
    if [ -n "$latest" ] && [ -f "${latest}scripts/validate_plugin.py" ]; then
        echo "${latest}"
    else
        echo ""
    fi
}

# Read plugin list and GitHub repos from marketplace.json
read_marketplace_plugins() {
    local marketplace_json="$MARKETPLACE_DIR/.claude-plugin/marketplace.json"
    if [ ! -f "$marketplace_json" ]; then
        echo "ERROR: marketplace.json not found at $marketplace_json" >&2
        exit 1
    fi
    # Output: name|repo lines
    python3 -c "
import json, sys
with open('$marketplace_json') as f:
    data = json.load(f)
for p in data.get('plugins', []):
    name = p.get('name', '')
    source = p.get('source', {})
    repo = ''
    if isinstance(source, dict):
        repo = source.get('repo', '')
    if name and repo:
        print(f'{name}|{repo}')
"
}

# ── Parse arguments ──────────────────────────────────────────────────

DRY_RUN=""
VALIDATE="yes"
declare -a REQUESTED_PLUGINS=()

for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN="yes"
    elif [ "$arg" = "--no-validate" ]; then
        VALIDATE=""
    elif [ "$arg" = "--strict" ]; then
        VALIDATE="yes"  # legacy alias
    else
        REQUESTED_PLUGINS+=("$arg")
    fi
done

# Track results
declare -a VALIDATED=()
declare -a VALIDATION_FAILED_LIST=()
declare -a SKIPPED=()

# ── Read plugins from marketplace.json ────────────────────────────────

declare -A PLUGIN_REPOS  # name -> github repo
declare -a ALL_PLUGIN_NAMES=()

while IFS='|' read -r name repo; do
    PLUGIN_REPOS["$name"]="$repo"
    ALL_PLUGIN_NAMES+=("$name")
done < <(read_marketplace_plugins)

# Filter to requested plugins if specified
if [ ${#REQUESTED_PLUGINS[@]} -gt 0 ]; then
    PLUGINS=()
    for req in "${REQUESTED_PLUGINS[@]}"; do
        if [ -n "${PLUGIN_REPOS[$req]+x}" ]; then
            PLUGINS+=("$req")
        else
            echo "ERROR: Unknown plugin '$req'"
            echo ""
            echo "Available plugins (from marketplace.json):"
            for p in "${ALL_PLUGIN_NAMES[@]}"; do echo "  - $p"; done
            exit 1
        fi
    done
else
    PLUGINS=("${ALL_PLUGIN_NAMES[@]}")
fi

PLUGIN_COUNT=${#PLUGINS[@]}
echo "============================================================"
echo "  Validate $PLUGIN_COUNT plugin(s) + push marketplace"
echo "============================================================"
if [ ${#REQUESTED_PLUGINS[@]} -gt 0 ]; then
    for p in "${PLUGINS[@]}"; do echo "  - $p"; done
fi
echo ""

# ── Pre-push validation ──────────────────────────────────────────────

if [ -n "$VALIDATE" ]; then
    CPV_DIR=$(find_cpv_dir)
    if [ -z "$CPV_DIR" ]; then
        echo "ERROR: CPV plugin not found in cache. Install it first:"
        echo "  claude /cpv-install-plugin claude-plugins-validation"
        exit 1
    fi

    VALIDATOR="$CPV_DIR/scripts/validate_plugin.py"
    MARKETPLACE_VALIDATOR="$CPV_DIR/scripts/validate_marketplace.py"

    echo "Using CPV from: $CPV_DIR"
    echo ""
    echo "--- plugin validation (--strict) ---"

    VALIDATION_FAILED=0
    CLONE_DIR=$(mktemp -d /tmp/cpv-validate-XXXXXX)
    trap "rm -rf '$CLONE_DIR'" EXIT

    set +e

    for plugin in "${PLUGINS[@]}"; do
        repo="${PLUGIN_REPOS[$plugin]}"
        clone_path="$CLONE_DIR/$plugin"
        echo -n "  $plugin (${repo})... "

        # Shallow clone from GitHub
        if ! gh repo clone "$repo" "$clone_path" -- --depth 1 -q 2>/dev/null; then
            echo "CLONE FAILED"
            VALIDATION_FAILED_LIST+=("$plugin (clone failed)")
            VALIDATION_FAILED=1
            continue
        fi

        # Run CPV with --strict (zero tolerance — even NIT blocks)
        VOUTPUT=$(cd "$CPV_DIR" && uv run python "$VALIDATOR" "$clone_path" --strict 2>&1)
        VCODE=$?
        if [ "$VCODE" -eq 0 ]; then
            echo "PASSED"
            VALIDATED+=("$plugin")
        else
            echo "BLOCKED (exit $VCODE)"
            echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR|MINOR|NIT" | head -10
            VALIDATION_FAILED_LIST+=("$plugin (exit $VCODE)")
            VALIDATION_FAILED=1
        fi
    done

    # Validate marketplace.json
    echo ""
    echo -n "  marketplace.json... "
    if [ -f "$MARKETPLACE_VALIDATOR" ]; then
        VOUTPUT=$(cd "$CPV_DIR" && uv run python "$MARKETPLACE_VALIDATOR" "$MARKETPLACE_DIR" --strict 2>&1)
        VCODE=$?
        if [ "$VCODE" -eq 0 ]; then
            echo "PASSED"
        else
            echo "BLOCKED (exit $VCODE)"
            echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR|MINOR|NIT" | head -10
            VALIDATION_FAILED=1
        fi
    else
        echo "SKIPPED (validator not found)"
    fi

    set -e

    echo ""
    if [ "$VALIDATION_FAILED" -eq 1 ]; then
        echo "ERROR: Validation failed. Fix ALL issues before pushing."
        echo ""
        echo "Failed plugins:"
        for f in "${VALIDATION_FAILED_LIST[@]}"; do echo "  ! $f"; done
        exit 1
    fi
    echo "  All validations passed."
    echo ""
fi

# ── Sync versions from GitHub into marketplace.json ──────────────────

echo "--- marketplace version sync ---"
cd "$MARKETPLACE_DIR"

if [ -f "scripts/sync_marketplace_versions.py" ]; then
    echo "  Syncing versions from GitHub..."
    uv run python scripts/sync_marketplace_versions.py --quiet 2>&1 || true
fi

# Check if marketplace.json changed
if ! git diff --quiet .claude-plugin/marketplace.json 2>/dev/null; then
    git add .claude-plugin/marketplace.json
    git commit -m "chore: sync marketplace.json plugin versions"
    echo "  Committed version sync"
fi

# ── Push marketplace ─────────────────────────────────────────────────

echo ""
echo "--- marketplace push ---"

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "main")
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "none")

if [ "$LOCAL" = "$REMOTE" ] && git diff --staged --quiet 2>/dev/null; then
    echo "  SKIP: marketplace already up to date"
    SKIPPED+=("marketplace (up to date)")
else
    if [ -n "$DRY_RUN" ]; then
        echo "  DRY-RUN: would push marketplace to origin/$BRANCH"
        SKIPPED+=("marketplace (dry-run)")
    else
        MARKETPLACE_PUSHED=0
        for attempt in 1 2 3; do
            echo "  Push attempt $attempt/3..."
            git pull origin "$BRANCH" --rebase 2>&1 || true
            if git push origin "$BRANCH" 2>&1; then
                MARKETPLACE_PUSHED=1
                break
            fi
            echo "  Push attempt $attempt failed, retrying in 5s..."
            sleep 5
        done
        if [ "$MARKETPLACE_PUSHED" -eq 1 ]; then
            echo "  PUSHED marketplace"
        else
            echo "  FAILED marketplace (after 3 attempts)"
            echo ""
            exit 1
        fi
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  Results"
echo "============================================================"
echo ""
if [ ${#VALIDATED[@]} -gt 0 ]; then
    echo "  VALIDATED (${#VALIDATED[@]}):"
    for p in "${VALIDATED[@]}"; do echo "    ✓ $p"; done
fi
if [ ${#SKIPPED[@]} -gt 0 ]; then
    echo "  SKIPPED (${#SKIPPED[@]}):"
    for s in "${SKIPPED[@]}"; do echo "    - $s"; done
fi
echo ""
echo "Done."
