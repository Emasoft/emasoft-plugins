# Emasoft Plugins Marketplace

A collection of high-quality Claude Code plugins focused on productivity and workflow optimization.

<!-- PLUGIN-VERSIONS-START -->
## Plugin Versions

| Plugin | Version | Description |
|--------|---------|-------------|
| perfect-skill-suggester | 1.1.1 | High-accuracy skill activation (88%+) with AI-analyzed keywords |

*Last updated: 2026-01-23*

<!-- PLUGIN-VERSIONS-END -->

---

## Installation

### 1. Add Marketplace

```bash
claude plugin marketplace add https://github.com/Emasoft/emasoft-plugins
```

### 2. Install Plugin

```bash
claude plugin install perfect-skill-suggester@emasoft-plugins
```

### 3. Verify Installation

```bash
claude plugin list
```

### 4. Restart Claude Code

After installation, restart Claude Code for the plugin to take effect.

---

## Available Plugins

### [Perfect Skill Suggester (PSS)](./perfect-skill-suggester/README.md)

> **[Full Documentation](./perfect-skill-suggester/README.md)** | **[Architecture](./perfect-skill-suggester/docs/PSS-ARCHITECTURE.md)** | **[Changelog](./perfect-skill-suggester/CHANGELOG.md)**

High-accuracy skill activation with AI-analyzed keywords and Rust-powered matching.

**Features:**
- 88%+ accuracy on skill activation
- AI-analyzed keywords via Haiku agents
- Rust binary for ~10ms hook execution
- 70+ synonym expansion patterns
- Weighted scoring system
- Three-tier confidence routing (HIGH/MEDIUM/LOW)
- Co-usage boosting for related skills
- Multi-project skill discovery from `~/.claude.json`

**Commands:**
- `/pss-status` - View PSS status and index statistics
- `/pss-reindex-skills` - Regenerate skill index with AI analysis

**Requirements:**
- Pre-built binaries included for all platforms (macOS, Linux, Windows)
- Python 3.8+ for index generation

**Supported Platforms:**

| Platform | Binary |
|----------|--------|
| macOS Apple Silicon | `pss-darwin-arm64` |
| macOS Intel | `pss-darwin-x86_64` |
| Linux x86_64 | `pss-linux-x86_64` |
| Linux ARM64 | `pss-linux-arm64` |
| Windows x86_64 | `pss-windows-x86_64.exe` |

---

## For Developers

This section is for contributors who want to develop or modify the plugins.

### Clone the Repository

```bash
git clone https://github.com/Emasoft/emasoft-plugins.git
cd emasoft-plugins
```

### Local Testing

```bash
# Validate the marketplace
claude plugin validate .

# Validate a specific plugin
claude plugin validate ./perfect-skill-suggester

# Load plugin locally without installing
claude --plugin-dir ./perfect-skill-suggester
```

### Adding a Local Marketplace

For development, you can add the cloned repo as a local marketplace:

```bash
claude plugin marketplace add /path/to/emasoft-plugins
```

### Releasing New Versions

Use the release script for proper version bumping and tagging:

```bash
python release.py patch perfect-skill-suggester "Bug fix description"
python release.py minor perfect-skill-suggester "New feature"
python release.py major perfect-skill-suggester "Breaking change"
```

---

## License

MIT License - See individual plugin directories for specific licenses.

## Author

**Emasoft**
- GitHub: [@Emasoft](https://github.com/Emasoft)
- Email: 713559+Emasoft@users.noreply.github.com
