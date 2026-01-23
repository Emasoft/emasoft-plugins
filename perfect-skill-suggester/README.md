# Perfect Skill Suggester (PSS)

**High-accuracy skill activation (88%+) for Claude Code** with AI-analyzed keywords, weighted scoring, synonym expansion, and three-tier confidence routing.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Update to Latest Version](#update-to-latest-version)
- [Reinstall (Fix Broken Installation)](#reinstall-fix-broken-installation)
- [Uninstall](#uninstall)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [For Developers](#for-developers)
- [Documentation](#documentation)
- [License](#license)

---

## Features

### AI-Analyzed Keywords
Haiku subagents analyze each SKILL.md to extract optimal activation patterns. Instead of relying on manually defined keywords, the AI reads the skill content and determines what user prompts should trigger it.

### Native Rust Binary (~10ms)
A pre-compiled Rust binary handles all matching logic, keeping hook latency minimal. No Python interpreter startup, no JIT compilation - just fast native code.

### Synonym Expansion (70+ patterns)
User prompts are expanded with synonyms before matching. For example:
- `"pr"` → `"github pull request"`
- `"403"` → `"oauth2 authentication"`
- `"db"` → `"database"`
- `"ci"` → `"cicd deployment automation"`

### Weighted Scoring System
Different match types contribute different point values:
- **Directory match**: +5 points (skill is in a directory mentioned in prompt)
- **Path match**: +4 points (file paths in prompt match skill patterns)
- **Intent match**: +4 points (action verbs like "deploy", "test", "build")
- **Pattern match**: +3 points (regex patterns in skill config)
- **Keyword match**: +2 points (simple keyword matches)
- **First match bonus**: +10 points (first keyword hit gets extra weight)
- **Original bonus**: +3 points (keyword in original prompt, not from expansion)

### Three-Tier Confidence Routing
Match scores determine how suggestions are presented:
- **HIGH (≥12)**: Auto-suggest with commitment reminder
- **MEDIUM (6-11)**: Show with match evidence explaining why
- **LOW (<6)**: Include as alternatives for user consideration

### Commitment Mechanism
For HIGH confidence matches, output includes an evaluation reminder prompting Claude to pause and assess whether the skill truly fits the user's needs before blindly following instructions.

### Skills-First Ordering
In the hook output, matched skills appear before other context types, ensuring Claude sees relevant skills prominently.

### Fuzzy/Typo Tolerance (Damerau-Levenshtein)
Typos and transpositions are automatically corrected:
- `"gti"` matches `"git"` (transposition = 1 edit)
- `"dokcer"` matches `"docker"` (typo = 1 edit)
- Adaptive thresholds: 1 edit for short words, 2 for medium, 3 for long

### Task Decomposition
Complex multi-task prompts are automatically split and matched separately:
- `"set up docker and then configure ci"` → 2 sub-tasks
- Detects: conjunctions, semicolons, numbered/bulleted lists
- Scores are aggregated across sub-tasks

### Activation Logging
Privacy-preserving JSONL logs at `~/.claude/logs/pss-activations.jsonl`:
- Prompts truncated to 100 chars with SHA-256 hash
- Automatic rotation at ~10,000 entries
- Disable with `PSS_NO_LOGGING=1` env var

### Per-Skill Configuration (.pss files)
Each skill can have a `.pss` file for custom matching rules:
- Additional keywords beyond AI-analyzed defaults
- Negative keywords to prevent false matches
- Tier (primary/secondary/utility) for priority
- Score boost (-10 to +10)

---

## Installation

### Step 1: Add Marketplace

```bash
claude plugin marketplace add https://github.com/Emasoft/emasoft-plugins
```

### Step 2: Install Plugin

```bash
claude plugin install perfect-skill-suggester@emasoft-plugins
```

### Step 3: Verify Installation

```bash
claude plugin list
```

You should see:
```
❯ perfect-skill-suggester@emasoft-plugins
  Version: 1.1.1
  Scope: user
  Status: ✔ enabled
```

### Step 4: Restart Claude Code

**Important:** After installation, you must restart Claude Code for the plugin to take effect.

### Step 5: Generate Skill Index

After restarting, run the reindex command to analyze all skills with AI:

```
/pss-reindex-skills
```

---

## Update to Latest Version

When a new version is released, follow these steps:

### Step 1: Update Marketplace Cache

```bash
claude plugin marketplace update emasoft-plugins
```

### Step 2: Uninstall Current Version

```bash
claude plugin uninstall perfect-skill-suggester
```

### Step 3: Install Latest Version

```bash
claude plugin install perfect-skill-suggester@emasoft-plugins
```

### Step 4: Restart Claude Code

Restart Claude Code to load the updated plugin.

---

## Reinstall (Fix Broken Installation)

If the plugin is not working correctly, perform a clean reinstall:

### Step 1: Uninstall

```bash
claude plugin uninstall perfect-skill-suggester
```

### Step 2: Update Marketplace Cache

```bash
claude plugin marketplace update emasoft-plugins
```

### Step 3: Reinstall

```bash
claude plugin install perfect-skill-suggester@emasoft-plugins
```

### Step 4: Restart Claude Code

Restart Claude Code to load the freshly installed plugin.

---

## Uninstall

To completely remove the plugin:

### Step 1: Uninstall Plugin

```bash
claude plugin uninstall perfect-skill-suggester
```

### Step 2: (Optional) Remove Marketplace

If you no longer want plugins from this marketplace:

```bash
claude plugin marketplace remove emasoft-plugins
```

### Step 3: Restart Claude Code

Restart Claude Code to complete the removal.

---

## Quick Start

### 1. Generate Skill Index

Run the reindex command to analyze all skills with AI:

```
/pss-reindex-skills
```

This spawns Haiku subagents to analyze each SKILL.md and generate optimal activation keywords.

### 2. Check Status

```
/pss-status
```

View index statistics, cache validity, and scoring configuration.

### 3. Use Naturally

Just type your requests naturally. PSS will suggest relevant skills based on weighted keyword matching:

```
"help me set up github actions"
→ Suggests: devops-expert (HIGH confidence)
```

---

## Commands

### /pss-reindex-skills

Generate AI-analyzed keyword index for all skills.

```
/pss-reindex-skills [--force] [--skill SKILL_NAME] [--batch-size N]
```

| Flag | Description |
|------|-------------|
| `--force` | Force reindex even if cache is fresh |
| `--skill NAME` | Only reindex specific skill |
| `--batch-size N` | Skills per batch (default: 10) |

### /pss-status

View current status and test matching.

```
/pss-status [--verbose] [--test "PROMPT"]
```

| Flag | Description |
|------|-------------|
| `--verbose` | Show detailed breakdown |
| `--test "PROMPT"` | Test matching against prompt |

---

## How It Works

### Three-Phase Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                     USER PROMPT                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: SYNONYM EXPANSION (70+ patterns)                  │
│                                                             │
│  "pr" → "github pull request"                               │
│  "403" → "oauth2 authentication"                            │
│  "db" → "database"                                          │
│  "ci" → "cicd deployment automation"                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: WEIGHTED SCORING                                  │
│                                                             │
│  • directory match    +5 points                             │
│  • path match         +4 points                             │
│  • intent match       +4 points                             │
│  • pattern match      +3 points                             │
│  • keyword match      +2 points                             │
│  • first match bonus  +10 points                            │
│  • original bonus     +3 points (not from expansion)        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: CONFIDENCE CLASSIFICATION                         │
│                                                             │
│  HIGH (≥12):   Auto-suggest with commitment reminder        │
│  MEDIUM (6-11): Show with match evidence                    │
│  LOW (<6):      Include alternatives                        │
└─────────────────────────────────────────────────────────────┘
```

### Commitment Mechanism

For HIGH confidence matches, the output includes a commitment reminder:

```json
{
  "name": "devops-expert",
  "score": 0.95,
  "confidence": "HIGH",
  "commitment": "Before implementing: Evaluate YES/NO - Will this skill solve the user's actual problem?"
}
```

This helps Claude pause and evaluate before blindly following skill instructions.

---

## Configuration

### Scoring Weights

Modify weights in the Rust source at `rust/skill-suggester/src/main.rs`:

```rust
const WEIGHTS: MatchWeights = MatchWeights {
    directory: 5,
    path: 4,
    intent: 4,
    pattern: 3,
    keyword: 2,
    first_match: 10,
    original_bonus: 3,
    capped_max: 10,
};
```

### Confidence Thresholds

```rust
const HIGH_THRESHOLD: i32 = 12;
const MEDIUM_THRESHOLD: i32 = 6;
```

---

## Troubleshooting

### Commands not found after installation

**Symptom:** Plugin shows as installed and enabled, but `/pss-reindex-skills` or `/pss-status` commands are not found.

**Solution:** Restart Claude Code. Plugins only load their commands on startup.

### Plugin install fails

**Symptom:** `claude plugin install` returns an error.

**Solutions:**
1. Update the marketplace cache first:
   ```bash
   claude plugin marketplace update emasoft-plugins
   ```
2. Try reinstalling the marketplace:
   ```bash
   claude plugin marketplace remove emasoft-plugins
   claude plugin marketplace add https://github.com/Emasoft/emasoft-plugins
   ```

### Plugin shows as disabled

**Symptom:** Plugin is installed but status shows `✘ disabled`.

**Solution:** Enable the plugin:
```bash
claude plugin enable perfect-skill-suggester
```

### Hook not triggering

**Symptom:** Plugin is installed and enabled, but skill suggestions don't appear.

**Solutions:**
1. Verify the plugin is enabled: `claude plugin list`
2. Check hooks are registered: `/hooks` (inside Claude Code)
3. Restart Claude Code

### Skill index not generated

**Symptom:** `/pss-status` shows no skills indexed.

**Solution:** Run `/pss-reindex-skills` to generate the skill index.

### Binary not found or permission denied

**Symptom:** Hook fails with "binary not found" or "permission denied" error.

**Solutions:**
1. Check binary exists: `ls -la <plugin-path>/bin/`
2. Make binary executable: `chmod +x <plugin-path>/bin/pss-*`
3. Check platform: ensure you have the correct binary for your OS/architecture

### Python errors during reindex

**Symptom:** `/pss-reindex-skills` fails with Python errors.

**Solutions:**
1. Ensure Python 3.8+ is installed: `python3 --version`
2. Check script path: `<plugin-path>/scripts/pss_discover_skills.py`
3. Run script manually to see full error:
   ```bash
   python3 <plugin-path>/scripts/pss_discover_skills.py --help
   ```

### No skill suggestions appear (silent failure)

**Symptom:** Plugin is installed and working, but no skills are ever suggested, even for prompts that should match.

**Cause:** The skill index file doesn't exist at `~/.claude/cache/skill-index.json`. This happens when you haven't run `/pss-reindex-skills` after installation.

**Solution:** Run `/pss-reindex-skills` to generate the skill index:
```
/pss-reindex-skills
```

**Verify the index exists:**
```bash
ls -la ~/.claude/cache/skill-index.json
```

### "Failed to read skill index" error

**Symptom:** Error message mentioning "Failed to read skill index from <path>".

**Causes:**
- File permissions issue
- Disk full
- File corrupted

**Solutions:**
1. Check file exists: `ls -la ~/.claude/cache/skill-index.json`
2. Check permissions: `chmod 644 ~/.claude/cache/skill-index.json`
3. Regenerate index: `/pss-reindex-skills --force`

### "Failed to parse skill index" error

**Symptom:** Error message mentioning "Failed to parse skill index".

**Cause:** The skill index JSON file is corrupted or malformed.

**Solution:** Regenerate the index (it will overwrite the corrupted file):
```
/pss-reindex-skills --force
```

### Index exists but skills not matching

**Symptom:** Index file exists at `~/.claude/cache/skill-index.json` but skills that should match aren't being suggested.

**Causes:**
- Index is outdated (new skills added since last reindex)
- Keywords in index don't match your prompt
- Scoring threshold too high

**Solutions:**
1. Force reindex to pick up new skills:
   ```
   /pss-reindex-skills --force
   ```
2. Test matching with verbose output:
   ```
   /pss-status --test "your prompt here" --verbose
   ```
3. Check the skill's keywords in the index:
   ```bash
   cat ~/.claude/cache/skill-index.json | jq '.skills["skill-name"]'
   ```

---

## For Developers

This section is for contributors who want to develop, modify, or test the plugin locally.

### Development Setup

#### Option 1: Load Plugin Directly (Recommended)

The fastest way to test plugin changes without installing:

```bash
# Load the plugin directly from your development directory
claude --plugin-dir /path/to/perfect-skill-suggester
```

This loads the plugin for the current session only. Changes to plugin files require restarting Claude Code.

#### Option 2: Clone and Develop

```bash
# Clone the marketplace repo
git clone https://github.com/Emasoft/emasoft-plugins.git
cd emasoft-plugins/perfect-skill-suggester

# Make your changes...

# Test by loading the plugin directly
claude --plugin-dir .
```

### Project Structure

```
perfect-skill-suggester/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest (REQUIRED)
├── bin/                      # Pre-built Rust binaries
│   ├── pss-darwin-arm64      # macOS Apple Silicon
│   ├── pss-darwin-x86_64     # macOS Intel
│   ├── pss-linux-x86_64      # Linux x86_64
│   ├── pss-linux-arm64       # Linux ARM64
│   └── pss-windows-x86_64.exe # Windows
├── commands/                 # Slash commands
│   ├── pss-reindex-skills.md
│   └── pss-status.md
├── hooks/                    # Hook configurations
│   └── hooks.json
├── rust/                     # Rust source code
│   └── skill-suggester/
│       ├── Cargo.toml
│       └── src/main.rs
├── scripts/                  # Python scripts
│   ├── pss_discover_skills.py
│   ├── pss_hook.py
│   └── pss_validate_plugin.py
├── skills/                   # Skills provided by plugin
│   └── pss-usage/
└── docs/                     # Documentation
    ├── PSS-ARCHITECTURE.md
    └── PLUGIN-VALIDATION.md
```

### Local Testing Workflow

```bash
# 1. Make changes to plugin files

# 2. Validate the plugin structure
claude plugin validate .

# 3. Run the validation script
uv run python scripts/pss_validate_plugin.py --verbose

# 4. Test the plugin
claude --plugin-dir .

# 5. Inside Claude Code, test commands:
#    /pss-status
#    /pss-reindex-skills
```

### Building Rust Binary from Source

```bash
cd rust/skill-suggester
cargo build --release
```

Cross-compile for all platforms:

```bash
# macOS ARM64
cargo build --release --target aarch64-apple-darwin

# macOS x86_64
cargo build --release --target x86_64-apple-darwin

# Linux x86_64
cargo build --release --target x86_64-unknown-linux-gnu

# Linux ARM64
cargo build --release --target aarch64-unknown-linux-gnu

# Windows x86_64
cargo build --release --target x86_64-pc-windows-gnu
```

Copy binaries to `bin/` directory:

```bash
cp target/aarch64-apple-darwin/release/pss bin/pss-darwin-arm64
cp target/x86_64-apple-darwin/release/pss bin/pss-darwin-x86_64
# ... etc
```

### Validation Script

Run after every change to ensure plugin integrity:

```bash
uv run python scripts/pss_validate_plugin.py --verbose
```

This validates:
- Plugin manifest structure
- Command frontmatter
- Hook configuration
- Script syntax
- Binary presence

### Adding a Local Marketplace for Development

If you prefer installing the plugin during development:

```bash
# Add local marketplace
claude plugin marketplace add /path/to/emasoft-plugins

# Install from local marketplace
claude plugin install perfect-skill-suggester@emasoft-plugins

# After changes, update and reinstall
claude plugin marketplace update emasoft-plugins
claude plugin uninstall perfect-skill-suggester
claude plugin install perfect-skill-suggester@emasoft-plugins
```

### Important Notes for Developers

1. **No Hot-Reload**: Claude Code does not support hot-reloading plugins. After any change, you must restart Claude Code.

2. **Use `${CLAUDE_PLUGIN_ROOT}`**: Always use this environment variable in scripts and hooks for portable paths.

3. **Hook stdin/stdout**: Hooks receive input via stdin as JSON, not environment variables. Output JSON to stdout.

4. **Test on Multiple Platforms**: If modifying Rust code, test binaries on all supported platforms.

---

## Skill Index Format (v3.0)

```json
{
  "version": "3.0",
  "generated": "2026-01-18T06:00:00Z",
  "method": "ai-analyzed",
  "skills_count": 216,
  "skills": {
    "devops-expert": {
      "source": "user",
      "path": "/path/to/SKILL.md",
      "type": "skill",
      "keywords": ["github", "actions", "ci", "deploy"],
      "intents": ["deploy", "build", "test"],
      "patterns": ["workflow.*failed", "ci.*error"],
      "directories": ["workflows", ".github"],
      "description": "CI/CD pipeline configuration"
    }
  }
}
```

---

## Platform Support

Pre-built binaries included for:

| Platform | Binary |
|----------|--------|
| macOS Apple Silicon | `bin/pss-darwin-arm64` |
| macOS Intel | `bin/pss-darwin-x86_64` |
| Linux x86_64 | `bin/pss-linux-x86_64` |
| Linux ARM64 | `bin/pss-linux-arm64` |
| Windows x86_64 | `bin/pss-windows-x86_64.exe` |

---

## Performance

| Metric | Value |
|--------|-------|
| Hook execution | ~10ms |
| Binary size | ~1MB |
| Memory usage | ~2-3MB |
| Accuracy | 88%+ |

---

## Documentation

| Document | Description |
|----------|-------------|
| [PSS-ARCHITECTURE.md](docs/PSS-ARCHITECTURE.md) | Core architecture: two-pass generation, index as superset, categories vs keywords |
| [PLUGIN-VALIDATION.md](docs/PLUGIN-VALIDATION.md) | Guide for writing plugin validation scripts |

### Key Architecture Concepts

- **Index is a Superset**: The skill index contains ALL skills ever indexed. The agent filters suggestions against its context-injected available skills list.
- **No Staleness Checks**: Regenerate from scratch with `/pss-reindex-skills`. No incremental updates.
- **Two-Pass Generation**: Pass 1 extracts keywords/descriptions, Pass 2 uses AI to determine co-usage relationships.
- **Categories vs Keywords**: Categories are FIELDS OF COMPETENCE (16 predefined) for the CxC matrix. Keywords are a SUPERSET including specific tools/actions.

---

## License

MIT License - see [LICENSE](LICENSE)

## Author

Emasoft <713559+Emasoft@users.noreply.github.com>

## Repository

https://github.com/Emasoft/perfect-skill-suggester
