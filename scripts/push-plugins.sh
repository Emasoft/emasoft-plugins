#!/usr/bin/env bash
# Push plugin repos and marketplace sequentially.
# Usage: ./scripts/push-plugins.sh [plugin-name ...] [--dry-run]
#
# If no plugin names given, pushes ALL plugins.
# If plugin names given, pushes only those plugins.
#
# Before pushing:
#   - Validates ALL plugins and marketplace.json (zero tolerance for CRITICAL/MAJOR)
#   - Dereferences symlinks in scripts/ to real files (so GitHub repos are self-contained)
#   - Commits the dereferenced files
#   - Pushes
#   - Restores symlinks locally after push
#
# Validation is mandatory by default. Use --no-validate to skip (NOT recommended).
#
# After pushing plugins:
#   - Syncs marketplace.json versions from OUTPUT_SKILLS
#   - Pushes marketplace
#
# Examples:
#   ./scripts/push-plugins.sh                          # Push all plugins
#   ./scripts/push-plugins.sh emasoft-chat-history      # Push one plugin
#   ./scripts/push-plugins.sh perfect-skill-suggester claude-plugins-validation  # Push two
#   ./scripts/push-plugins.sh --dry-run                # Dry-run all
#   ./scripts/push-plugins.sh emasoft-chat-history --dry-run  # Dry-run one
#   ./scripts/push-plugins.sh --no-validate                    # Skip pre-push validation (NOT recommended)
#   ./scripts/push-plugins.sh emasoft-chat-history --no-validate  # Skip validation for one

set -euo pipefail

# Derive paths from the script's own location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_DIR="$MARKETPLACE_DIR/OUTPUT_SKILLS"
VALIDATOR="$BASE_DIR/claude-plugins-validation/scripts/validate_plugin.py"

# All known plugins in push order
ALL_PLUGINS=(
    "claude-plugins-validation"
    "perfect-skill-suggester"
    "emasoft-architect-agent"
    "emasoft-assistant-manager-agent"
    "emasoft-integrator-agent"
    "emasoft-orchestrator-agent"
    "emasoft-chief-of-staff"
    "emasoft-programmer-agent"
    "emasoft-chat-history"
)

# ── Parse arguments ──────────────────────────────────────────────────

DRY_RUN=""
VALIDATE="yes"  # Validation is ON by default (was --strict opt-in, now default)
declare -a REQUESTED_PLUGINS=()

for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN="--dry-run"
    elif [ "$arg" = "--no-validate" ]; then
        VALIDATE=""
    elif [ "$arg" = "--strict" ]; then
        # Legacy alias, still works (validation is default now)
        VALIDATE="yes"
    else
        REQUESTED_PLUGINS+=("$arg")
    fi
done

# If no plugins specified, push all
if [ ${#REQUESTED_PLUGINS[@]} -eq 0 ]; then
    PLUGINS=("${ALL_PLUGINS[@]}")
else
    # Validate requested plugin names
    PLUGINS=()
    for req in "${REQUESTED_PLUGINS[@]}"; do
        found=0
        for known in "${ALL_PLUGINS[@]}"; do
            if [ "$req" = "$known" ]; then
                found=1
                break
            fi
        done
        if [ "$found" -eq 1 ]; then
            PLUGINS+=("$req")
        else
            echo "ERROR: Unknown plugin '$req'"
            echo ""
            echo "Available plugins:"
            for p in "${ALL_PLUGINS[@]}"; do echo "  - $p"; done
            exit 1
        fi
    done
fi

# Track results
declare -a PUSHED=()
declare -a SKIPPED=()
declare -a FAILED=()

# ── Validation scripts sync ────────────────────────────────────────────

# ── Validation scripts sync ────────────────────────────────────────────

sync_validation_scripts() {
    # Copy ALL validate_*.py scripts from the CPV plugin into the target plugin.
    # This ensures every published plugin is self-contained with the latest validators.
    # Also removes obsolete prefixed validators (e.g., epa_validate_plugin.py).
    # Skips the CPV plugin itself (it already has the originals).
    local plugin_dir="$1"
    local plugin_name="$2"
    local cpv_scripts="$BASE_DIR/claude-plugins-validation/scripts"
    local scripts_dir="$plugin_dir/scripts"

    if [ "$plugin_name" = "claude-plugins-validation" ]; then
        return
    fi

    if [ ! -d "$cpv_scripts" ]; then
        echo "  WARNING: CPV scripts dir not found, skipping validation sync"
        return
    fi

    mkdir -p "$scripts_dir"

    # Remove old prefixed validators (e.g., epa_validate_plugin.py, eaa_validate_plugin.py)
    local removed=0
    for old in "$scripts_dir"/*_validate_plugin.py "$scripts_dir"/*_validate_marketplace.py "$scripts_dir"/*_validate_hook.py "$scripts_dir"/*_validate_skill.py "$scripts_dir"/*_validate.py; do
        if [ -f "$old" ] && [ "$(basename "$old")" != "validate_plugin.py" ]; then
            rm "$old"
            removed=$((removed + 1))
        fi
    done
    if [ "$removed" -gt 0 ]; then
        echo "  Removed $removed obsolete prefixed validator(s)"
    fi

    # Copy all validate_*.py, validation_common.py, and smart_exec.py from CPV
    local synced=0
    for src in "$cpv_scripts"/validate_*.py "$cpv_scripts"/validation_common.py "$cpv_scripts"/smart_exec.py; do
        [ -f "$src" ] || continue
        local filename
        filename=$(basename "$src")
        local dst="$scripts_dir/$filename"
        if [ -f "$dst" ] && diff -q "$src" "$dst" >/dev/null 2>&1; then
            continue  # already up to date
        fi
        cp "$src" "$dst"
        chmod +x "$dst"
        synced=$((synced + 1))
    done

    if [ "$synced" -gt 0 ]; then
        echo "  Synced $synced validation script(s) from CPV"
    fi
}

# ── Symlink dereference/restore helpers ──────────────────────────────

dereference_symlinks() {
    # Replace symlinks in scripts/ with real file copies for publishing.
    # Saves a map file to /tmp so we can restore after push.
    local plugin_dir="$1"
    local plugin_name="$2"
    local scripts_dir="$plugin_dir/scripts"
    local map_file="/tmp/.symlink_map_${plugin_name}"

    rm -f "$map_file"

    if [ ! -d "$scripts_dir" ]; then
        return
    fi

    local found=0
    for f in "$scripts_dir"/*; do
        if [ -L "$f" ]; then
            local rel_target
            rel_target=$(readlink "$f")             # original relative symlink target
            local abs_target
            abs_target=$(readlink -f "$f" 2>/dev/null || echo "")  # resolved absolute path
            if [ -n "$abs_target" ] && [ -f "$abs_target" ]; then
                echo "$(basename "$f")|$rel_target" >> "$map_file"
                rm "$f"
                cp "$abs_target" "$f"
                found=$((found + 1))
            else
                echo "  WARNING: broken symlink $f -> $rel_target (target not found, skipping)"
            fi
        fi
    done

    if [ "$found" -gt 0 ]; then
        echo "  Dereferenced $found symlink(s) in scripts/"
    fi
}

restore_symlinks() {
    # Restore symlinks from the saved map file after push.
    local plugin_dir="$1"
    local plugin_name="$2"
    local scripts_dir="$plugin_dir/scripts"
    local map_file="/tmp/.symlink_map_${plugin_name}"

    if [ ! -f "$map_file" ]; then
        return
    fi

    while IFS='|' read -r filename rel_target; do
        local link_path="$scripts_dir/$filename"
        if [ -f "$link_path" ] || [ -L "$link_path" ]; then
            rm "$link_path"
        fi
        ln -s "$rel_target" "$link_path"
    done < "$map_file"

    rm -f "$map_file"
    echo "  Restored symlinks in scripts/"
}

# ── Main ─────────────────────────────────────────────────────────────

PLUGIN_COUNT=${#PLUGINS[@]}
if [ "$PLUGIN_COUNT" -eq ${#ALL_PLUGINS[@]} ]; then
    echo "============================================================"
    echo "  Push All Plugins (sequential)"
    echo "============================================================"
else
    echo "============================================================"
    echo "  Push $PLUGIN_COUNT plugin(s) (sequential)"
    echo "============================================================"
    for p in "${PLUGINS[@]}"; do echo "  - $p"; done
fi
echo ""

# ── Pre-push validation (runs by default, skip with --no-validate) ───
if [ -n "$VALIDATE" ]; then
    echo "--- pre-push validation ---"
    if [ ! -f "$VALIDATOR" ]; then
        echo "  ERROR: Plugin validator not found at $VALIDATOR"
        exit 1
    fi
    VALIDATOR_DIR="$BASE_DIR/claude-plugins-validation"
    MARKETPLACE_VALIDATOR="$VALIDATOR_DIR/scripts/validate_marketplace.py"
    VALIDATION_FAILED=0

    # Temporarily disable set -e so validation failures don't kill the script
    set +e

    # Validate each plugin
    # Exit codes: 0=clean, 1=CRITICAL, 2=MAJOR, 3=MINOR-only
    # Block push on CRITICAL (1) or MAJOR (2). MINOR-only (3) is allowed.
    for plugin in "${PLUGINS[@]}"; do
        plugin_dir="$BASE_DIR/$plugin"
        echo -n "  Validating $plugin... "
        # Run validator from its own directory so uv picks up its dependencies
        VOUTPUT=$(cd "$VALIDATOR_DIR" && uv run python "$VALIDATOR" "$plugin_dir" 2>&1)
        VCODE=$?
        if [ "$VCODE" -eq 0 ]; then
            echo "PASSED (clean)"
        elif [ "$VCODE" -eq 3 ]; then
            echo "PASSED (minor issues only)"
        else
            echo "BLOCKED (exit code $VCODE)"
            echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR" | head -5
            echo "  BLOCKED: $plugin has CRITICAL/MAJOR issues"
            VALIDATION_FAILED=1
        fi
    done

    # Validate marketplace.json
    if [ -f "$MARKETPLACE_VALIDATOR" ]; then
        echo -n "  Validating marketplace.json... "
        VOUTPUT=$(cd "$VALIDATOR_DIR" && uv run python "$MARKETPLACE_VALIDATOR" "$MARKETPLACE_DIR" 2>&1)
        VCODE=$?
        if [ "$VCODE" -eq 0 ]; then
            echo "PASSED (clean)"
        elif [ "$VCODE" -eq 3 ]; then
            echo "PASSED (minor issues only)"
        else
            echo "BLOCKED (exit code $VCODE)"
            echo "$VOUTPUT" | grep -E "CRITICAL|MAJOR" | head -5
            echo "  BLOCKED: marketplace.json has CRITICAL/MAJOR issues"
            VALIDATION_FAILED=1
        fi
    else
        echo "  WARNING: Marketplace validator not found at $MARKETPLACE_VALIDATOR"
    fi

    # Re-enable set -e
    set -e

    echo ""
    if [ "$VALIDATION_FAILED" -eq 1 ]; then
        echo "ERROR: Pre-push validation failed (CRITICAL/MAJOR issues). Fix before pushing."
        exit 1
    fi
    echo "  All validations passed."
    echo ""
fi

# Phase 1: Push each plugin repo
for plugin in "${PLUGINS[@]}"; do
    plugin_dir="$BASE_DIR/$plugin"
    echo "--- $plugin ---"

    if [ ! -d "$plugin_dir/.git" ]; then
        echo "  SKIP: no git repo"
        SKIPPED+=("$plugin (no git)")
        echo ""
        continue
    fi

    cd "$plugin_dir"

    # Sync latest validation scripts from CPV
    sync_validation_scripts "$plugin_dir" "$plugin"

    # Dereference any remaining symlinks in scripts/ for publishing
    dereference_symlinks "$plugin_dir" "$plugin"

    # Stage any synced or dereferenced files
    git add scripts/ 2>/dev/null || true
    if ! git diff --staged --quiet 2>/dev/null; then
        git commit -m "chore: sync validation scripts from CPV"
        echo "  Committed updated scripts"
    fi

    # Check if there are unpushed commits
    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    # Determine default branch
    BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "main")
    REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "none")

    if [ "$LOCAL" = "$REMOTE" ]; then
        # Nothing to push -- restore symlinks and skip
        restore_symlinks "$plugin_dir" "$plugin"
        echo "  SKIP: already up to date ($BRANCH)"
        SKIPPED+=("$plugin (up to date)")
        echo ""
        continue
    fi

    AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo "?")
    echo "  $AHEAD commit(s) ahead of origin/$BRANCH"

    if [ "$DRY_RUN" = "--dry-run" ]; then
        # Restore symlinks on dry-run
        restore_symlinks "$plugin_dir" "$plugin"
        echo "  DRY-RUN: would push to origin/$BRANCH"
        SKIPPED+=("$plugin (dry-run)")
    else
        if git push origin "$BRANCH" 2>&1; then
            # Also push any tags
            if git push origin --tags 2>&1; then
                echo "  PUSHED (with tags)"
            else
                echo "  PUSHED (branch only, tags failed)"
            fi
            PUSHED+=("$plugin")
        else
            echo "  FAILED"
            FAILED+=("$plugin")
        fi
        # Restore symlinks after push (local working tree goes back to symlinks)
        restore_symlinks "$plugin_dir" "$plugin"
    fi
    echo ""

    # Small delay to avoid GitHub rate limits
    sleep 2
done

# Brief wait for GitHub to propagate pushed refs
echo "Waiting 5s for GitHub to propagate pushed refs..."
sleep 5

# Phase 2: Update marketplace versions and push
echo "--- marketplace ---"
cd "$MARKETPLACE_DIR"

# Sync versions from OUTPUT_SKILLS to marketplace.json
if [ -f "scripts/sync_marketplace_versions.py" ]; then
    echo "  Syncing versions from OUTPUT_SKILLS..."
    uv run python scripts/sync_marketplace_versions.py --quiet 2>&1 || true
fi

# Check if marketplace.json changed
if ! git diff --quiet .claude-plugin/marketplace.json 2>/dev/null; then
    git add .claude-plugin/marketplace.json
    git commit -m "chore: sync marketplace.json plugin versions"
fi

# Pull remote changes (from auto-update workflows) and push
BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "main")
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "none")

if [ "$LOCAL" = "$REMOTE" ] && git diff --staged --quiet 2>/dev/null; then
    echo "  SKIP: marketplace already up to date"
    SKIPPED+=("marketplace (up to date)")
else
    if [ "$DRY_RUN" = "--dry-run" ]; then
        echo "  DRY-RUN: would push marketplace"
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
            FAILED+=("marketplace")
        fi
    fi
fi

# Summary
echo ""
echo "============================================================"
echo "  Results"
echo "============================================================"
echo ""
if [ ${#PUSHED[@]} -gt 0 ]; then
    echo "  PUSHED (${#PUSHED[@]}):"
    for p in "${PUSHED[@]}"; do echo "    + $p"; done
fi
if [ ${#SKIPPED[@]} -gt 0 ]; then
    echo "  SKIPPED (${#SKIPPED[@]}):"
    for s in "${SKIPPED[@]}"; do echo "    - $s"; done
fi
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "  FAILED (${#FAILED[@]}):"
    for f in "${FAILED[@]}"; do echo "    ! $f"; done
    echo ""
    exit 1
fi
echo ""
echo "Done."
