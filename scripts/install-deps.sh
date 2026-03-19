#!/bin/bash
# Install all dependencies including dev dependencies
set -e

echo "📦 Installing all dependencies..."
uv sync --all-extras

echo "✅ All dependencies installed!"
echo ""
echo "Installed tools:"
echo "  - pre-commit: $(pre-commit --version)"
echo "  - pytest: $(pytest --version | head -1)"
echo "  - mypy: $(mypy --version)"
echo "  - ruff: $(ruff --version)"
echo "  - black: $(black --version)"