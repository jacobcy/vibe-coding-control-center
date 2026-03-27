#!/usr/bin/env zsh
# scripts/github/create_issue.sh
# 通用 GitHub issue 创建工具（使用 GitHub API，避免 gh CLI 权限限制）
#
# Usage:
#   zsh scripts/github/create_issue.sh --title "bug: ..." --body "复现步骤..."
#   zsh scripts/github/create_issue.sh --title "..." --body-file /tmp/body.md --label "bug,improvement"
#   zsh scripts/github/create_issue.sh --title "..." --body "..." --dry-run
#
# Options:
#   --title      <str>   Issue 标题（必填）
#   --body       <str>   Issue 正文（与 --body-file 二选一）
#   --body-file  <path>  从文件读取正文（与 --body 二选一）
#   --label      <str>   逗号分隔的 label 列表（可选，默认: improvement）
#   --repo       <str>   owner/repo 格式（可选，默认从 git remote 自动检测）
#   --dry-run            预览，不实际创建

set -e

TITLE=""
BODY=""
BODY_FILE=""
LABEL="improvement"
REPO=""
DRY_RUN=0

# --- 参数解析 ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)     TITLE="$2";     shift 2 ;;
    --body)      BODY="$2";      shift 2 ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    --label)     LABEL="$2";     shift 2 ;;
    --repo)      REPO="$2";      shift 2 ;;
    --dry-run)   DRY_RUN=1;      shift   ;;
    --help)
      sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# --- 校验 ---
if [[ -z "$TITLE" ]]; then
  echo "ERROR: --title is required" >&2; exit 1
fi
if [[ -z "$BODY" && -z "$BODY_FILE" ]]; then
  echo "ERROR: --body or --body-file is required" >&2; exit 1
fi
if [[ -n "$BODY" && -n "$BODY_FILE" ]]; then
  echo "ERROR: --body and --body-file are mutually exclusive" >&2; exit 1
fi
if [[ -n "$BODY_FILE" ]]; then
  [[ -f "$BODY_FILE" ]] || { echo "ERROR: body-file not found: $BODY_FILE" >&2; exit 1; }
  BODY=$(cat "$BODY_FILE")
fi

# --- 自动检测 repo ---
if [[ -z "$REPO" ]]; then
  REMOTE_URL=$(git remote get-url origin 2>/dev/null) || { echo "ERROR: cannot detect git remote" >&2; exit 1; }
  # 支持 https://github.com/owner/repo.git 和 git@github.com:owner/repo.git
  REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] Would create issue in $REPO:"
  echo "  Title : $TITLE"
  echo "  Label : $LABEL"
  echo "  Body  : $(echo "$BODY" | head -3)..."
  exit 0
fi

# --- 获取 token ---
GH_TOKEN=$(gh auth token 2>/dev/null) || { echo "ERROR: gh auth token failed" >&2; exit 1; }

# --- 构建 payload ---
PAYLOAD=$(python3 -c "
import json, sys
title, body, label = sys.argv[1], sys.argv[2], sys.argv[3]
labels = [l.strip() for l in label.split(',') if l.strip()]
print(json.dumps({'title': title, 'body': body, 'labels': labels}))
" "$TITLE" "$BODY" "$LABEL")

# --- 调用 API ---
RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/$REPO/issues" \
  -d "$PAYLOAD")

NUM=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('number',''))" 2>/dev/null)
URL=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('html_url',''))" 2>/dev/null)

if [[ -z "$NUM" || "$NUM" == "None" ]]; then
  echo "FAILED to create issue" >&2
  echo "$RESP" | python3 -m json.tool 2>/dev/null | head -20 >&2
  exit 1
fi

echo "Created #$NUM: $TITLE"
echo "  $URL"

