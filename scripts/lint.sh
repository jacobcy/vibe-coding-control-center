#!/usr/bin/env bash
# scripts/lint.sh — Dual-layer shell lint: zsh -n (syntax) + shellcheck (quality)
set -e

echo "=== Layer 1: Zsh Syntax Check (zsh -n) ==="
errors=0
for f in lib/*.sh bin/vibe; do
  if zsh -n "$f" 2>&1; then
    echo "  ✅ $f"
  else
    echo "  ❌ $f"
    errors=$((errors + 1))
  fi
done
[[ $errors -gt 0 ]] && { echo "FAIL: $errors files have syntax errors"; exit 1; }
echo "  All files passed syntax check."

echo ""
echo "=== Layer 2: ShellCheck Lint ==="
shellcheck -s bash -S error lib/*.sh bin/vibe
echo "  All files passed ShellCheck (error level)."

echo ""
echo "=== Layer 2b: ShellCheck Warnings (informational) ==="
shellcheck -s bash -S warning lib/*.sh bin/vibe || true
echo ""
echo "✅ Lint complete. 0 errors."
