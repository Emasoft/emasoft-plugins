#!/usr/bin/env bash
# Validate and push local plugin repos, then push marketplace.
# Usage: ./scripts/push-plugins.sh [/path/to/plugin ...] [--dry-run] [--no-validate]
#
# Each path must be a local git clone of a plugin repo.
# The script:
#   1. Validates each local plugin with CPV validate_plugin.py --strict
#   2. Pushes each plugin to its own git origin
#   3. Syncs marketplace.json versions
#   4. Validates marketplace with CPV validate_marketplace.py --strict
#   5. Pushes the marketplace repo
#
# If no plugin paths given, only the marketplace is validated and pushed.
#
# Examples:
#   ./scripts/push-plugins.sh ~/Code/my-plugin                # One plugin + marketplace
#   ./scripts/push-plugins.sh ~/Code/plugin1 ~/Code/plugin2   # Multiple + marketplace
#   ./scripts/push-plugins.sh --dry-run ~/Code/my-plugin      # Validate only, no push
#   ./scripts/push-plugins.sh                                 # Marketplace only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find the CPV validator from the plugin cache (latest installed version)
find_cpv_dir() {
    local cache_base="$HOME/.claude/plugins/cache/emasoft-plugins/claude-plugins-validation"
    if [ ! -d "$cache_base" ]; then
        echo ""
        return
    fi
    local latest
    latest=$(ls -1d "$cache_base"/*/ 2>/dev/null | sort -t/ -k"$(echo "$cache_base" | tr -cd '/' | wc -c | tr -d ' ')" -V | tail -1)
    if [ -n "$latest" ] && [ -f "${latest}scripts/validate_plugin.py" ]; then
        echo "${latest}"
    else
        echo ""
    fi
}

# ── Parse arguments ──────────────────────────────────────────────────

DRY_RUN=""
VALIDATE="yes"
declare -a PLUGIN_PATHS=()

for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN="yes"
    elif [ "$arg" = "--no-validate" ]; then
        VALIDATE=""
    else
        # Resolve to absolute path
        resolved="$(cd "$arg" 2>/dev/null && pwd)" || {
            echo "ERROR: '$arg' is not a valid directory"
            exit 1
        }
        PLUGIN_PATHS+=("$resolved")
    fi
done

# Track results
declare -a VALIDATED=()
declare -a PUSHED=()
declare -a VALIDATION_FAILED_LIST=()
declare -a PUSH_FAILED_LIST=()
declare -a SKIPPED=()

PLUGIN_COUNT=${#PLUGIN_PATHS[@]}
echo "============================================================"
if [ "$PLUGIN_COUNT" -gt 0 ]; then
    echo "  Validate + push $PLUGIN_COUNT plugin(s) + marketplace"
else
    echo "  Push marketplace only (no plugin paths given)"
fi
echo "============================================================"
for p in "${PLUGIN_PATHS[@]}"; do echo "  - $p"; done
echo ""

# ── Find CPV ─────────────────────────────────────────────────────────

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

# ── Validate + push each plugin ──────────────────────────────────────

VALIDATION_FAILED=0

if [ "$PLUGIN_COUNT" -gt 0 ]; then
    echo "--- plugin validation + push (--strict) ---"

    set +e

    for plugin_path in "${PLUGIN_PATHS[@]}"; do
        plugin_name=$(basename "$plugin_path")
        echo -n "  $plugin_name ($plugin_path)... "

        # Verify it's a git repo
        if [ ! -d "$plugin_path/.git" ]; then
            echo "NOT A GIT REPO"
            VALIDATION_FAILED_LIST+=("$plugin_name (not a git repo)")
            VALIDATION_FAILED=1
            continue
        fi

        # Verify it has plugin.json
        if [ ! -f "$plugin_path/.claude-plugin/plugin.json" ]; then
            echo "NOT A PLUGIN (no .claude-plugin/plugin.json)"
            VALIDATION_FAILED_LIST+=("$plugin_name (not a plugin)")
            VALIDATION_FAILED=1
            continue
        fi

        # Validate with CPV --strict
        if [ -n "$VALIDATE" ]; then
            VOUTPUT=$(cd "$CPV_DIR" && uv run python "$VALIDATOR" "$plugin_path" --strict 2>&1)
            VCODE=$?
            if [ "$VCODE" -eq 0 ]; then
                echo -n "PASSED "
                VALIDATED+=("$plugin_name")
            else
                echo "BLOCKED (exit $VCODE)"
                echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR|MINOR|NIT" | head -10
                VALIDATION_FAILED_LIST+=("$plugin_name (exit $VCODE)")
                VALIDATION_FAILED=1
                continue
            fi
        fi

        # Push to origin
        BRANCH=$(cd "$plugin_path" && git symbolic-ref --short HEAD 2>/dev/null || echo "main")
        if [ -n "$DRY_RUN" ]; then
            echo "DRY-RUN (would push to origin/$BRANCH)"
            SKIPPED+=("$plugin_name (dry-run)")
        else
            if (cd "$plugin_path" && git push origin "$BRANCH" 2>&1); then
                echo "PUSHED"
                PUSHED+=("$plugin_name")
            else
                echo "PUSH FAILED"
                PUSH_FAILED_LIST+=("$plugin_name")
            fi
        fi
    done

    set -e

    echo ""
    if [ "$VALIDATION_FAILED" -eq 1 ]; then
        echo "ERROR: Validation failed for some plugins. Fix issues before pushing."
        echo ""
        echo "Failed:"
        for f in "${VALIDATION_FAILED_LIST[@]}"; do echo "  ! $f"; done
        exit 1
    fi
fi

# ── Validate marketplace ─────────────────────────────────────────────

echo "--- marketplace validation (--strict) ---"

if [ -n "$VALIDATE" ] && [ -f "$MARKETPLACE_VALIDATOR" ]; then
    echo -n "  marketplace.json... "
    set +e
    VOUTPUT=$(cd "$CPV_DIR" && uv run python "$MARKETPLACE_VALIDATOR" "$MARKETPLACE_DIR" --strict 2>&1)
    VCODE=$?
    set -e
    if [ "$VCODE" -eq 0 ]; then
        echo "PASSED"
    else
        echo "BLOCKED (exit $VCODE)"
        echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR|MINOR|NIT" | head -10
        echo ""
        echo "ERROR: Marketplace validation failed. Fix issues before pushing."
        exit 1
    fi
else
    echo "  SKIPPED"
fi
echo ""

# ── Sync versions into marketplace.json ──────────────────────────────

echo "--- marketplace version sync ---"
cd "$MARKETPLACE_DIR"

if [ -f "scripts/sync_marketplace_versions.py" ]; then
    echo "  Syncing versions..."
    uv run python scripts/sync_marketplace_versions.py --quiet 2>&1 || true
fi

# Commit if marketplace.json changed
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
            PUSHED+=("marketplace")
        else
            echo "  FAILED marketplace (after 3 attempts)"
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
if [ ${#PUSHED[@]} -gt 0 ]; then
    echo "  PUSHED (${#PUSHED[@]}):"
    for p in "${PUSHED[@]}"; do echo "    ✓ $p"; done
fi
if [ ${#SKIPPED[@]} -gt 0 ]; then
    echo "  SKIPPED (${#SKIPPED[@]}):"
    for s in "${SKIPPED[@]}"; do echo "    - $s"; done
fi
if [ ${#PUSH_FAILED_LIST[@]} -gt 0 ]; then
    echo "  PUSH FAILED (${#PUSH_FAILED_LIST[@]}):"
    for f in "${PUSH_FAILED_LIST[@]}"; do echo "    ✗ $f"; done
fi
echo ""
echo "Done."
