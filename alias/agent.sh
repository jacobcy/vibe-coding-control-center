#!/usr/bin/env zsh
# @desc Claude: 新建会话 + 跳过权限
# @featured
alias cci='claude --dangerously-skip-permissions'

# @desc Claude: 恢复会话 + 跳过权限
# @featured
alias cc='claude -c --dangerously-skip-permissions'

# @desc Codex: 新建会话 + 全自动
# @featured
alias cxi='codex --full-auto'

# @desc Codex: 恢复会话 + 全自动
# @featured
alias cx='codex resume --last --full-auto'

# @desc OpenCode: 新建会话
# @featured
alias oci='opencode'

# @desc OpenCode: 恢复会话
# @featured
alias oc='opencode -c'

# @desc Gemini: 新建会话 + 跳过权限
# @featured
alias gmi='gemini --yolo'

# @desc Gemini: 恢复会话 + 跳过权限
# @featured
alias gm='gemini -r latest --yolo'
