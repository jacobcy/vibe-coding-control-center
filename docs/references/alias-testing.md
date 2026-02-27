# Alias Testing Guide

## Quick Start

```bash
# Run all tests
zsh tests/test-aliases.sh

# Quiet mode (results only)
zsh tests/test-aliases.sh --quiet

# Verbose mode (detailed output)
zsh tests/test-aliases.sh --verbose
```

## What Gets Tested

### 1. Syntax Validation
All alias files are checked for valid zsh syntax:
- `config/aliases.sh` (main entry point)
- `config/aliases/claude.sh` (Claude commands)
- `config/aliases/opencode.sh` (OpenCode commands)
- `config/aliases/openspec.sh` (OpenSpec commands)
- `config/aliases/vibe.sh` (Vibe commands)
- `config/aliases/git.sh` (Git helpers)
- `config/aliases/tmux.sh` (Tmux commands)
- `config/aliases/worktree.sh` (Worktree management)

### 2. Function Tests
Key functions are tested for correct operation:
- `vibe_has()` - Command existence check
- `vibe_now()` - Timestamp generation
- `vibe_git_root()` - Git repository detection
- `vibe_branch()` - Current branch detection

### 3. Dependency Checks
Required and optional dependencies:
- Required: `git`, `zsh`
- Optional: `tmux`, `lazygit`, `claude`, `opencode`

## CI/CD Integration

GitHub Actions workflow automatically runs tests on:
- Push to main branch (when alias files change)
- Pull requests (when alias files change)
- Ubuntu and macOS runners

See `.github/workflows/test-aliases.yml`

## Troubleshooting

### Test Hangs
If tests hang during execution:
```bash
# Use quiet mode to minimize output
zsh tests/test-aliases.sh --quiet

# Or run specific test sections
zsh -c 'source tests/test-aliases.sh; run_syntax_tests'
```

### Syntax Errors
If syntax check fails:
```bash
# Check specific file
zsh -n config/aliases.sh

# Check with verbose output
zsh -vx config/aliases.sh 2>&1 | head -50
```

### Missing Dependencies
If dependency tests fail:
```bash
# Check which commands are missing
which git zsh tmux lazygit claude opencode

# Install missing commands (macOS)
brew install git zsh tmux lazygit

# Install missing commands (Ubuntu)
sudo apt-get install git zsh tmux
```

## Contributing

When adding new aliases:

1. Add corresponding tests in `tests/test-aliases.sh`
2. Run full test suite before committing
3. Update this documentation if needed

## Test Output Example

```
╔════════════════════════════════════════════════════════════╗
║          Vibe Alias 测试套件 (Test Suite)                  ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║              语法检查测试 (Syntax Tests)                     ║
╚════════════════════════════════════════════════════════════╝

[TEST] 语法检查: aliases.sh
[PASS] 语法检查: aliases.sh
...

╔════════════════════════════════════════════════════════════╗
║                    测试总结 (Test Summary)                 ║
╚════════════════════════════════════════════════════════════╝

  总测试数: 35
  通过: 35
  失败: 0
  跳过: 0

✓ 所有测试通过!
```
