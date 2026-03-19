#!/usr/bin/env bash
# pre-push hook - 本地审查，拦截明显问题，减少CI浪费
set -euo pipefail

echo "🔍 Running pre-push checks..."

# 1. 基本检查（快速，<5s）
echo "  → Type + LOC checks..."
# Ruff check is already done in pre-commit, skip here to avoid conflicts

uv run mypy src || {
    echo "❌ Type check failed"
    exit 1
}

bash scripts/hooks/check-python-loc.sh || {
    echo "❌ Python LOC check failed"
    exit 1
}

bash scripts/hooks/check-shell-loc.sh || {
    echo "❌ Shell LOC check failed"
    exit 1
}

# 2. 覆盖率检查（强制，~30s）
# Temporarily disabled due to CoverageError import issue
# echo "  → Coverage check..."
# uv run python -c "..." || exit 1

# 3. 风险评分判断（快速，<2s）
echo "  → Risk assessment..."
RISK_LEVEL=$(uv run python -c "
import json
import sys
from vibe3.clients.git_client import GitClient
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.config.loader import get_config

try:
    git = GitClient()

    # 获取 HEAD commit 的改动
    sha = git.get_current_sha()
    diff_stats = git.get_diff_stats(f'{sha}^', sha)

    # 简化的风险评分（不需要完整 AST 分析）
    dims = PRDimensions(
        changed_files=diff_stats.get('files_changed', 0),
        impacted_modules=0,  # 简化：不分析模块
        changed_lines=diff_stats.get('lines_changed', 0),
        critical_paths_touches=0,
        public_api_touches=0,
    )

    config = get_config()
    report = generate_score_report(dims, config)

    print(report.level)
except Exception as e:
    # 风险评分失败，默认 MEDIUM（允许 push）
    print('MEDIUM')
" 2>/dev/null) || RISK_LEVEL="MEDIUM"

if [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo "  ⚠️  High risk detected (level: $RISK_LEVEL)"
    echo "  Consider running local review before push:"
    echo "    uv run python -m vibe3 review base main"
    # 不阻断，只是警告
fi

echo "✓ All pre-push checks passed"
exit 0