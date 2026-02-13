# CLAUDE.md - Emasoft Plugins Marketplace

## CRITICAL: RELEASING PLUGINS TO MARKETPLACE (MANDATORY WORKFLOW)

**ALWAYS use `release-plugin.py` to publish plugins. NEVER push manually or use `push_all_plugins.sh` for releases.**

The release script handles the entire publish pipeline: validation, version bumping, git commits, tags, marketplace sync, and push.

### Location

```
./scripts/release-plugin.py
```

### Usage

```bash
# Release a single plugin with auto-version (patch bump)
uv run python scripts/release-plugin.py perfect-skill-suggester

# Release with specific version
uv run python scripts/release-plugin.py perfect-skill-suggester --version 2.0.0

# Release multiple plugins
uv run python scripts/release-plugin.py perfect-skill-suggester claude-plugins-validation

# Release ALL plugins at once
uv run python scripts/release-plugin.py

# Non-interactive mode (CI/CD or scripted releases)
uv run python scripts/release-plugin.py --yes

# Strict mode (fail on ANY warning, not just errors)
uv run python scripts/release-plugin.py --strict

# Dry run (see what would happen without changing anything)
uv run python scripts/release-plugin.py --dry-run

# Combined flags
uv run python scripts/release-plugin.py --yes --strict --dry-run
```

### Flags

| Flag | Description |
|------|-------------|
| `--yes` / `-y` | Auto-confirm all prompts. Auto-selects patch version when no `--version` given. |
| `--version X.Y.Z` | Set explicit version (single plugin only). |
| `--strict` | Fail on ANY validation warning or lint issue, not just errors. |
| `--dry-run` | Show what would happen without making changes. |

### What the Script Does (per plugin)

1. Validates plugin structure with the universal validator (`claude-plugins-validation`)
2. Runs the plugin's own internal validator (e.g., `pss_validate_plugin.py`)
3. Validates individual skills with `skills-ref`
4. Lints Python scripts with `ruff` and Bash scripts with `shellcheck`
5. Checks for uncommitted changes
6. Bumps version in `plugin.json`
7. Commits version bump in plugin sub-repo
8. Creates git tag
9. After all plugins: syncs `marketplace.json` versions and commits marketplace

### Backward Compatibility

The old single-plugin syntax still works:
```bash
uv run python scripts/release-plugin.py <plugin-name> <version>
```

---

## Marketplace Architecture (3-Repo System)

```
Plugin Repos (8 repos)          Marketplace Repo (this repo)
  push to main                     receives repository_dispatch
  notify-marketplace.yml  ───>     update-submodules.yml
                                   sync_marketplace_versions.py
                                   Auto-commit + push
```

### Plugins (as git submodules)

| Plugin | Prefix | Description |
|--------|--------|-------------|
| `claude-plugins-validation` | `cpv-` | Plugin/skill/agent validation |
| `perfect-skill-suggester` | `pss-` | AI-analyzed skill activation |
| `emasoft-architect-agent` | `eaa-` | Architecture design, planning |
| `emasoft-assistant-manager-agent` | `eama-` | User interface, role routing |
| `emasoft-integrator-agent` | `eia-` | Code review, quality gates |
| `emasoft-orchestrator-agent` | `eoa-` | Task distribution, delegation |
| `emasoft-chief-of-staff` | `ecos-` | Coordination, agent lifecycle |
| `emasoft-programmer-agent` | `epa-` | Implementation, coding |

### Key Files

| File | Purpose |
|------|---------|
| `scripts/release-plugin.py` | THE official release tool (use this!) |
| `.claude-plugin/marketplace.json` | Plugin registry with versions |
| `.gitmodules` | Git submodule configuration |
| `scripts/sync_marketplace_versions.py` | Syncs plugin.json versions to marketplace.json |
| `.github/workflows/update-submodules.yml` | Auto-updates submodules on dispatch |
| `CHANGELOG.md` | Auto-generated changelog |

### marketplace.json Source Format

For local submodule-based marketplaces:
```json
{
  "plugins": {
    "perfect-skill-suggester": {
      "version": "1.9.0",
      "description": "...",
      "source": "./perfect-skill-suggester"
    }
  }
}
```

**CRITICAL**: `source` must be a STRING path for local submodules, NOT an object.

---

## Plugin Installation (for Users)

```bash
# Add marketplace
claude plugin marketplace add https://github.com/Emasoft/emasoft-plugins

# Install a plugin
claude plugin install perfect-skill-suggester@emasoft-plugins

# RESTART Claude Code (required!)
```

### Update Workaround (Claude Code v2.1.37 bug)

Claude Code's `marketplace update` does NOT run `git submodule update`. After updating:

```bash
cd ~/.claude/plugins/marketplaces/emasoft-plugins
git submodule update --init --recursive
```

Then uninstall + reinstall the plugin and restart Claude Code.

---

## Validation

```bash
# Validate the marketplace itself
uv run python claude-plugins-validation/scripts/validate_marketplace.py . --verbose

# Validate a specific plugin
uv run python claude-plugins-validation/scripts/validate_plugin.py ./perfect-skill-suggester --verbose
```
