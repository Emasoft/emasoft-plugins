# Python Code Quality Audit Report
**Date**: 2026-01-23
**Target**: `/Users/emanuelesabetta/Code/SKILL_FACTORY/OUTPUT_SKILLS/emasoft-plugins-marketplace`

---

## Summary

| Check | Result | Details |
|-------|--------|---------|
| **Ruff Linting** | 338 issues | 61 auto-fixable |
| **Mypy Type Checking** | PASSED | No issues in 5 source files |

---

## Files Audited

### claude-plugins-validation/scripts/
- `validate_hook.py`
- `validate_marketplace.py`
- `validate_mcp.py`
- `validate_plugin.py`
- `validate_skill.py`

### perfect-skill-suggester/scripts/
- `pss_build.py`
- `pss_discover_skills.py`
- `pss_generate.py`
- `pss_hook.py`
- `pss_setup.py`
- `pss_validate.py`
- `pss_validate_marketplace.py`
- `pss_validate_plugin.py`

### scripts/ (root)
- `pre-commit-hook.py`
- `pre-push-hook.py`
- `release-plugin.py`
- `setup-hooks.py`
- `sync-versions.py`
- `verify-release.py`

### skills/plugin-validation-skill/references/
- `pre-push-hook.py`

---

## Issue Categories

### 1. Critical: Complexity Issues (C901, PLR0912, PLR0915)

Functions exceeding complexity thresholds (cognitive complexity > 10, branches > 12, statements > 50):

| File | Function | Issue |
|------|----------|-------|
| `validate_hook.py:398` | `lint_python_script` | C901 (14 > 10), PLR0912 (17 > 12) |
| `validate_hook.py:550` | `validate_command_hook` | C901 (13 > 10) |
| `validate_marketplace.py:281` | `validate_plugin_entry` | C901 (19 > 10), PLR0912 (18 > 12) |
| `validate_marketplace.py:419` | `validate_plugin_source` | C901 (12 > 10), PLR0912 (13 > 12) |
| `validate_marketplace.py:734` | `validate_github_deployment` | C901 (13 > 10), PLR0912 (13 > 12) |
| `validate_marketplace.py:814` | `validate_readme_content` | C901 (11 > 10) |
| `validate_marketplace.py:898` | `validate_marketplace` | C901 (11 > 10) |
| `validate_marketplace.py:994` | `format_report` | C901 (19 > 10), PLR0912 (15 > 12), PLR0915 (57 > 50) |
| `validate_mcp.py:222` | `validate_mcp_server` | C901 (35 > 10), PLR0912 (45 > 12), PLR0915 (83 > 50) |
| `validate_mcp.py:380` | `validate_mcp_config` | C901 (13 > 10) |
| `validate_mcp.py:459` | `validate_plugin_mcp` | C901 (12 > 10), PLR0912 (15 > 12) |
| `validate_plugin.py:124` | `validate_manifest` | C901 (22 > 10), PLR0912 (24 > 12) |
| `validate_plugin.py:476` | `validate_scripts` | C901 (17 > 10), PLR0912 (20 > 12) |
| `pss_discover_skills.py:110` | `get_all_skill_locations` | C901 (29 > 10), PLR0912 (28 > 12), PLR0915 (54 > 50) |
| `pss_discover_skills.py:282` | `discover_skills` | C901 (13 > 10), PLR0912 (14 > 12) |
| `pss_generate.py:88` | `extract_keywords_from_content` | C901 (17 > 10), PLR0912 (16 > 12) |
| `pss_validate.py:50` | `validate_pss_file` | C901 (51 > 10), PLR0912 (54 > 12), PLR0915 (125 > 50) |
| `pss_validate_marketplace.py:91` | `print_report` | C901 (16 > 10), PLR0912 (16 > 12) |
| `pss_validate_marketplace.py:160` | `validate_source` | C901 (17 > 10), PLR0912 (23 > 12) |
| `pss_validate_marketplace.py:241` | `validate_plugin_entry` | C901 (24 > 10), PLR0912 (27 > 12), PLR0915 (55 > 50) |
| `pss_validate_marketplace.py:357` | `validate_marketplace` | C901 (23 > 10), PLR0912 (30 > 12), PLR0915 (64 > 50) |
| `pss_validate_plugin.py:134` | `validate_manifest` | C901 (20 > 10), PLR0912 (21 > 12) |
| `pss_validate_plugin.py:319` | `validate_categories` | C901 (14 > 10), PLR0912 (14 > 12) |
| `pss_validate_plugin.py:529` | `validate_scripts` | C901 (15 > 10), PLR0912 (18 > 12) |
| `pre-commit-hook.py:188` | `main` | C901 (15 > 10), PLR0912 (20 > 12), PLR0915 (61 > 50) |
| `pre-push-hook.py:78` | `validate_plugin_manifest` | C901 (12 > 10) |
| `pre-push-hook.py:122` | `validate_hooks_config` | C901 (11 > 10) |
| `release-plugin.py:167` | `main` | C901 (39 > 10), PLR0911 (10 > 6), PLR0912 (45 > 12), PLR0915 (186 > 50) |
| `sync-versions.py:100` | `sync_versions` | C901 (19 > 10), PLR0912 (20 > 12) |
| `pss_build.py:214` | `main` | C901 (12 > 10), PLR0911 (9 > 6) |
| `pss_generate.py:409` | `main` | PLR0911 (7 > 6) |

**Recommendation**: Refactor these functions by:
- Breaking into smaller helper functions
- Using early returns to reduce nesting
- Extracting validation logic into separate methods

---

### 2. Security: subprocess.run without explicit check (PLW1510)

**Count**: 32 occurrences

All `subprocess.run()` calls lack explicit `check=False`:

| File | Line |
|------|------|
| `validate_hook.py` | 357, 403, 440, 484 |
| `validate_plugin.py` | 495, 517, 546 |
| `pss_build.py` | 68, 82, 114, 160, 197 |
| `pss_setup.py` | 97, 121, 214, 264 |
| `pss_hook.py` | 68 |
| `pss_validate_plugin.py` | 542, 558, 588 |
| `pre-commit-hook.py` | 34, 190 |
| `pre-push-hook.py` | 35, 257 |
| `release-plugin.py` | 55 |
| `verify-release.py` | 63 |
| `pre-push-hook.py` (skills) | 34, 257 |

**Fix**: Add explicit `check=False` to all subprocess.run() calls:
```python
result = subprocess.run(cmd, capture_output=True, check=False)
```

---

### 3. Security: Blind Exception Handling (BLE001)

**Count**: 18 occurrences

Catching bare `Exception` hides errors:

| File | Line |
|------|------|
| `validate_hook.py` | 394, 432, 471, 522 |
| `validate_marketplace.py` | 209, 651, 828 |
| `pss_discover_skills.py` | 105, 277, 351 |
| `pss_generate.py` | 331, 351, 479 |
| `pss_hook.py` | 87 |
| `pre-commit-hook.py` | 42 |
| `pre-push-hook.py` | 45 |
| `release-plugin.py` | 67 |
| `verify-release.py` | 73 |
| `pre-push-hook.py` (skills) | 44 |

**Fix**: Catch specific exceptions instead of bare `Exception`:
```python
except (ValueError, OSError) as e:
    # handle specific errors
```

---

### 4. Code Style: Line Length (E501)

**Count**: 40+ occurrences

Lines exceeding 88 characters (default ruff limit, project uses 120).

**Files with most violations**:
- `release-plugin.py`
- `pre-push-hook.py`
- `verify-release.py`
- `sync-versions.py`

**Fix**: Break long lines or increase line-length in ruff config.

---

### 5. Code Style: Import Sorting (I001)

**Count**: 9 files with unsorted imports

| File |
|------|
| `pss_build.py` |
| `pss_discover_skills.py` |
| `pss_generate.py` |
| `pss_validate.py` |
| `pre-commit-hook.py` |
| `pre-push-hook.py` |
| `release-plugin.py` |
| `setup-hooks.py` |
| `verify-release.py` |

**Fix**: Run `ruff check --select I --fix` to auto-sort imports.

---

### 6. Best Practices: Path.open() instead of open() (PTH123)

**Count**: 30+ occurrences

Using `open()` instead of `Path.open()`:

**Fix**:
```python
# Instead of:
with open(file_path) as f:
    data = f.read()

# Use:
with file_path.open() as f:
    data = f.read()
```

---

### 7. Best Practices: Unnecessary else after return (RET505)

**Count**: 15 occurrences

**Fix**:
```python
# Instead of:
if condition:
    return x
else:
    return y

# Use:
if condition:
    return x
return y
```

---

### 8. Best Practices: Nested if statements (SIM102)

**Count**: 12 occurrences

**Fix**: Combine nested if statements with `and`:
```python
# Instead of:
if a:
    if b:
        do_something()

# Use:
if a and b:
    do_something()
```

---

### 9. Performance: List Comprehensions (PERF401)

**Count**: 11 occurrences

Using loops instead of list comprehensions:

| File | Line |
|------|------|
| `validate_marketplace.py` | 294, 363, 494 |
| `pss_generate.py` | 176, 215 |
| `pss_validate.py` | 279, 341 |
| `pre-push-hook.py` | 250 |
| `verify-release.py` | 255 |
| `pre-push-hook.py` (skills) | 249 |

**Fix**:
```python
# Instead of:
results = []
for item in items:
    if condition:
        results.append(transform(item))

# Use:
results = [transform(item) for item in items if condition]
```

---

### 10. Code Style: Single vs Double Quotes (Q000, Q001, Q003)

**Count**: 20+ occurrences in `pss_hook.py`

Single quotes used where double quotes preferred.

**Fix**: Run `ruff check --select Q --fix` to auto-fix quote style.

---

### 11. File Permission Issues (EXE001)

**Count**: 3 files with shebang but not executable

| File |
|------|
| `validate_marketplace.py` |
| `validate_mcp.py` |
| `validate_plugin.py` |

**Fix**: `chmod +x <file>` or remove shebang if not meant to be executable.

---

### 12. Loop Variable Overwrite (PLW2901)

**Count**: 6 occurrences

Overwriting loop variable inside loop:

| File | Line | Variable |
|------|------|----------|
| `validate_hook.py` | 292 | `part` |
| `pss_generate.py` | 132, 153 | `word` |
| `pss_generate.py` | 221, 222 | `intent` |

**Fix**: Use a different variable name:
```python
for raw_word in words:
    word = raw_word.strip()
```

---

### 13. Exception Messages (EM102, TRY003)

**Count**: 6 occurrences

Using f-strings in exception messages:

| File | Line |
|------|------|
| `pss_generate.py` | 258 |
| `pss_hook.py` | 41, 53 |

**Fix**:
```python
# Instead of:
raise ValueError(f"Invalid value: {value}")

# Use:
msg = f"Invalid value: {value}"
raise ValueError(msg)
```

---

### 14. Deprecated Aliases (UP024)

**Count**: 6 occurrences in `sync-versions.py`

Using `IOError` instead of `OSError`:

**Fix**: Replace `IOError` with `OSError` (they are aliases in Python 3).

---

### 15. Import at Top Level (PLC0415)

**Count**: 3 occurrences

Imports inside functions:

| File | Line |
|------|------|
| `pss_generate.py` | 411 |
| `pss_validate.py` | 302 |
| `pss_setup.py` | 187 |

**Fix**: Move imports to top of file or keep if intentionally lazy-loaded.

---

## Auto-Fixable Issues

**61 issues** can be auto-fixed with:
```bash
cd /Users/emanuelesabetta/Code/SKILL_FACTORY/OUTPUT_SKILLS/emasoft-plugins-marketplace
uv run ruff check --select=ALL . --ignore=D,ANN,COM,ERA,T20,FBT,PLR0913,PLR2004,S603,S607,S101 --fix
```

For unsafe fixes (30 additional):
```bash
uv run ruff check --select=ALL . --ignore=D,ANN,COM,ERA,T20,FBT,PLR0913,PLR2004,S603,S607,S101 --fix --unsafe-fixes
```

---

## Recommendations

### High Priority
1. **Refactor complex functions** - Functions with 30+ branches are unmaintainable
2. **Add explicit `check=False`** to subprocess.run calls
3. **Replace blind `except Exception`** with specific exceptions

### Medium Priority
4. **Use `Path.open()`** instead of built-in `open()`
5. **Fix import sorting** (auto-fixable)
6. **Remove unnecessary else** after return statements

### Low Priority
7. **Use list comprehensions** for better performance
8. **Fix quote style** consistency (auto-fixable)
9. **Make scripts executable** or remove shebangs

---

## Mypy Results

**PASSED** - No type errors found in the 5 source files checked:
- `claude-plugins-validation/scripts/` (all 5 .py files)

---

## Commands Used

```bash
# Ruff linting
cd /Users/emanuelesabetta/Code/SKILL_FACTORY/OUTPUT_SKILLS/emasoft-plugins-marketplace
uv run ruff check --select=ALL . --ignore=D,ANN,COM,ERA,T20,FBT,PLR0913,PLR2004,S603,S607,S101

# Mypy type checking
cd /Users/emanuelesabetta/Code/SKILL_FACTORY/OUTPUT_SKILLS/emasoft-plugins-marketplace/claude-plugins-validation
uv run mypy scripts/ --ignore-missing-imports
```
