#!/usr/bin/env zsh
# Vibe3 development aliases

# @desc Install all dependencies (main + dev)
# @featured
alias v3-install='uv sync --all-extras'

# @desc Run tests with uv
# @featured
alias v3-test='uv run pytest'

# @desc Run type checking
alias v3-mypy='uv run mypy src'

# @desc Format code (black + ruff)
alias v3-fmt='uv run black src tests && uv run ruff check src tests --fix'

# @desc Run pre-commit checks
alias v3-check='uv run pre-commit run --all-files'

# @desc Run vibe3 CLI
# @featured
alias v3='uv run vibe3'

# @desc Run all development checks (format, type-check, test)
v3-dev() {
  echo "🔧 Running development checks..."
  echo ""
  echo "1️⃣  Formatting code..."
  uv run black src tests
  uv run ruff check src tests --fix
  echo ""
  echo "2️⃣  Type checking..."
  uv run mypy src
  echo ""
  echo "3️⃣  Running tests..."
  uv run pytest
  echo ""
  echo "✅ All checks completed!"
}