#!/bin/bash
# setup-hooks.sh - Install git hooks for marketplace and all submodules
# Run this after cloning to set up all git hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Setting up git hooks for emasoft-plugins-marketplace..."
echo "Repository root: $REPO_ROOT"

# Check if git-cliff is installed
if ! command -v git-cliff &> /dev/null; then
    echo "Warning: git-cliff is not installed. Install it with: brew install git-cliff"
fi

# =============================================================================
# Main repository hooks
# =============================================================================

MAIN_HOOKS_DIR="$REPO_ROOT/.git/hooks"

# Create post-commit hook for main repo
cat > "$MAIN_HOOKS_DIR/post-commit" << 'EOF'
#!/bin/bash
# post-commit hook: Update CHANGELOG.md using git-cliff

set -e

if ! command -v git-cliff &> /dev/null; then
    echo "Warning: git-cliff not found, skipping changelog generation"
    exit 0
fi

REPO_ROOT=$(git rev-parse --show-toplevel)

if [ ! -f "$REPO_ROOT/cliff.toml" ]; then
    echo "Warning: cliff.toml not found, skipping changelog generation"
    exit 0
fi

echo "Generating CHANGELOG.md..."
cd "$REPO_ROOT"
git-cliff -o CHANGELOG.md

if git diff --quiet CHANGELOG.md 2>/dev/null; then
    echo "CHANGELOG.md is up to date"
else
    echo "CHANGELOG.md updated - remember to commit it!"
fi

exit 0
EOF
chmod +x "$MAIN_HOOKS_DIR/post-commit"
echo "✓ Created main repo post-commit hook"

# Create pre-commit hook for main repo (version sync)
cat > "$MAIN_HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# pre-commit hook: Sync plugin versions from submodules to marketplace.json

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
SYNC_SCRIPT="$REPO_ROOT/scripts/sync-versions.py"

if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "Warning: sync-versions.py not found, skipping version sync"
    exit 0
fi

echo "Syncing plugin versions..."
python3 "$SYNC_SCRIPT" "$REPO_ROOT"

if ! git diff --quiet .claude-plugin/marketplace.json 2>/dev/null; then
    echo "marketplace.json was updated with new plugin versions"
    git add .claude-plugin/marketplace.json
    echo "Staged marketplace.json for commit"
fi

exit 0
EOF
chmod +x "$MAIN_HOOKS_DIR/pre-commit"
echo "✓ Created main repo pre-commit hook"

# =============================================================================
# Submodule hooks
# =============================================================================

# Function to set up hooks for a submodule
setup_submodule_hooks() {
    local submodule_name="$1"
    local submodule_path="$REPO_ROOT/$submodule_name"
    local hooks_dir="$REPO_ROOT/.git/modules/$submodule_name/hooks"

    if [ ! -d "$hooks_dir" ]; then
        echo "✗ Submodule $submodule_name not found or not initialized"
        return 1
    fi

    # Create post-commit hook
    cat > "$hooks_dir/post-commit" << EOF
#!/bin/bash
# post-commit hook: Update CHANGELOG.md using git-cliff

set -e

if ! command -v git-cliff &> /dev/null; then
    echo "Warning: git-cliff not found, skipping changelog generation"
    exit 0
fi

REPO_ROOT=\$(git rev-parse --show-toplevel)

if [ ! -f "\$REPO_ROOT/cliff.toml" ]; then
    echo "Warning: cliff.toml not found, skipping changelog generation"
    exit 0
fi

echo "Generating CHANGELOG.md for $submodule_name..."
cd "\$REPO_ROOT"
git-cliff -o CHANGELOG.md

if git diff --quiet CHANGELOG.md 2>/dev/null; then
    echo "CHANGELOG.md is up to date"
else
    echo "CHANGELOG.md updated - remember to commit it!"
fi

exit 0
EOF
    chmod +x "$hooks_dir/post-commit"
    echo "✓ Created $submodule_name post-commit hook"
}

# Set up hooks for each submodule
setup_submodule_hooks "perfect-skill-suggester"
setup_submodule_hooks "claude-plugins-validation"

echo ""
echo "All git hooks have been set up successfully!"
echo ""
echo "Hook summary:"
echo "  Main repo:"
echo "    - pre-commit: Syncs plugin versions to marketplace.json"
echo "    - post-commit: Generates CHANGELOG.md with git-cliff"
echo "  Submodules:"
echo "    - post-commit: Generates CHANGELOG.md with git-cliff"
