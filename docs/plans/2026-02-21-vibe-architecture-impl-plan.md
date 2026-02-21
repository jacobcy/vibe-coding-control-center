# Vibe 环境架构重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Vibe Coding 环境从分散的配置管理重构为工程化的模块化架构，支持双轨交互（结构化命令 + 自然语言）

**Architecture:** 采用统一清单模式（vibe.yaml），支持多密钥组切换，vibe chat 作为智能入口

**Tech Stack:** Zsh shell 脚本，YAML 配置，符号链接

---

## Phase 1: 核心架构（目录结构和配置系统）

### Task 1: 创建新目录结构模板

**Files:**
- Create: `lib/vibe_dir_template.sh` - 目录结构模板生成器

**Step 1: 编写目录模板生成脚本**

```bash
#!/usr/bin/env zsh
# lib/vibe_dir_template.sh

create_vibe_dir_structure() {
    local vibe_home="${1:-$HOME/.vibe}"

    mkdir -p "$vibe_home"/{keys,tools/claude,tools/opencode,mcp,skills,cache}

    # 创建 vibe.yaml 主配置
    cat > "$vibe_home/vibe.yaml" << 'EOF'
version: "1.0"
name: "vibe-env"

keys:
  current: anthropic

tools:
  claude:
    enabled: true
    default: true
  opencode:
    enabled: true

mcp:
  - github

defaults:
  editor: cursor
  shell: zsh
EOF

    # 创建示例密钥组
    cat > "$vibe_home/keys/anthropic.env" << 'EOF'
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5
EOF

    cat > "$vibe_home/keys/openai.env" << 'EOF'
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com
EOF

    # 创建 current 符号链接
    ln -sfn "$vibe_home/keys/anthropic.env" "$vibe_home/keys/current"

    echo "Created vibe directory structure at: $vibe_home"
}
```

**Step 2: 运行测试验证**

```bash
# 手动测试
zsh -c 'source lib/vibe_dir_template.sh; create_vibe_dir_structure /tmp/test-vibe'
ls -la /tmp/test-vibe/
# 预期: vibe.yaml, keys/, tools/, mcp/, skills/, cache/ 目录
```

**Step 3: 提交**

```bash
git add lib/vibe_dir_template.sh
git commit -m "feat: add vibe directory structure template"
```

---

### Task 2: 实现 vibe.yaml 解析器

**Files:**
- Modify: `lib/config.sh` - 添加 YAML 解析能力

**Step 1: 添加 YAML 解析函数**

```bash
# 在 lib/config.sh 中添加

parse_vibe_yaml() {
    local yaml_file="${1:-$VIBE_HOME/vibe.yaml}"

    if [[ ! -f "$yaml_file" ]]; then
        log_warn "vibe.yaml not found at: $yaml_file"
        return 1
    fi

    # 简单的 YAML 解析（避免外部依赖）
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 跳过注释和空行
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue

        # 解析 key: value 格式
        if [[ "$line" =~ ^[[:space:]]*([a-zA-Z_][a-zA-Z0-9_-]*):[[:space:]]*(.*) ]]; then
            local key="${match[1]}"
            local value="${match[2]}"
            value="${value%"${value##*[![:space:]]}"}"  # trim trailing whitespace
            VIBE_CONFIG[$key]="$value"
        fi
    done < "$yaml_file"

    return 0
}

get_current_keys_group() {
    local current_link="$VIBE_HOME/keys/current"

    if [[ -L "$current_link" ]]; then
        basename "$(readlink -f "$current_link")" .env
    else
        echo "anthropic"  # 默认
    fi
}
```

**Step 2: 测试 YAML 解析**

```bash
# 创建测试 YAML
echo 'version: "1.0"
name: test-env
keys:
  current: openai' > /tmp/test.yaml

# 测试函数（需要在 zsh 环境）
```

**Step 3: 提交**

```bash
git add lib/config.sh
git commit -m "feat: add vibe.yaml parser to config.sh"
```

---

## Phase 2: 密钥管理命令实现

### Task 3: 实现 vibe keys 子命令

**Files:**
- Create: `bin/vibe-keys` - 密钥管理入口
- Create: `lib/keys_manager.sh` - 密钥管理库

**Step 1: 创建密钥管理库**

```bash
#!/usr/bin/env zsh
# lib/keys_manager.sh

source "$(dirname "${(%):-%x}")/utils.sh"

VIBE_KEYS_DIR="${VIBE_HOME:-$HOME/.vibe/keys}"

vibe_keys_list() {
    echo "Available key groups:"
    for f in "$VIBE_KEYS_DIR"/*.env; do
        [[ -f "$f" ]] || continue
        basename "$f" .env
    done
}

vibe_keys_use() {
    local group="$1"

    if [[ -z "$group" ]]; then
        log_error "Key group name required"
        echo "Usage: vibe keys use <group-name>"
        return 1
    fi

    local target="$VIBE_KEYS_DIR/${group}.env"

    if [[ ! -f "$target" ]]; then
        log_error "Key group not found: $group"
        log_info "Available groups:"
        vibe_keys_list
        return 1
    fi

    # 更新符号链接
    rm -f "$VIBE_KEYS_DIR/current"
    ln -s "${group}.env" "$VIBE_KEYS_DIR/current"

    log_success "Switched to key group: $group"
}

vibe_keys_current() {
    local current="$(get_current_keys_group)"
    echo "Current key group: $current"
}

vibe_keys_set() {
    local key_value="$1"

    if [[ -z "$key_value" ]]; then
        log_error "Key=value required"
        return 1
    fi

    if [[ ! "$key_value" =~ ^([A-Z_][A-Z0-9_]*)=(.*) ]]; then
        log_error "Invalid format. Use KEY=value"
        return 1
    fi

    local key="${match[1]}"
    local value="${match[2]}"

    local current_group="$(get_current_keys_group)"
    local keys_file="$VIBE_KEYS_DIR/${current_group}.env"

    # 检查 key 是否已存在
    if grep -q "^${key}=" "$keys_file" 2>/dev/null; then
        # 更新
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$keys_file"
    else
        # 添加
        echo "${key}=${value}" >> "$keys_file"
    fi

    log_success "Set $key in group: $current_group"
}
```

**Step 2: 创建 vibe-keys 命令入口**

```bash
#!/usr/bin/env zsh
# bin/vibe-keys

set -e

# 加载配置
source "$(dirname "${(%):-%x}")/../lib/config.sh"
source "$(dirname "${(%):-%x}")/../lib/keys_manager.sh"

# 解析子命令
subcmd="${1:-}"
shift || true

case "$subcmd" in
    list)
        vibe_keys_list
        ;;
    use)
        vibe_keys_use "$@"
        ;;
    current)
        vibe_keys_current
        ;;
    set)
        vibe_keys_set "$@"
        ;;
    -h|--help)
        echo "Usage: vibe keys <command>"
        echo ""
        echo "Commands:"
        echo "  list              List all key groups"
        echo "  use <group>      Switch to a key group"
        echo "  current          Show current key group"
        echo "  set KEY=value    Set a key in current group"
        ;;
    *)
        echo "Unknown command: $subcmd"
        echo "Run 'vibe keys --help' for usage"
        exit 1
        ;;
esac
```

**Step 3: 提交**

```bash
git add bin/vibe-keys lib/keys_manager.sh
git commit -m "feat: implement vibe keys command"
```

---

### Task 4: 更新 bin/vibe 调度器支持 keys 子命令

**Files:**
- Modify: `bin/vibe` - 添加 keys 子命令支持

**Step 1: 修改 vibe 调度器**

```bash
# 在 bin/vibe 的 subcmd 处理中添加：

keys)
    exec "${VIBE_ROOT}/bin/vibe-keys" "$@"
    ;;
```

**Step 2: 测试**

```bash
# 创建测试环境
mkdir -p /tmp/test-vibe/keys
echo "TEST_KEY=value" > /tmp/test-vibe/keys/anthropic.env
ln -s anthropic.env /tmp/test-vibe/keys/current

VIBE_HOME=/tmp/test-vibe bin/vibe keys list
# 预期: anthropic

VIBE_HOME=/tmp/test-vibe bin/vibe keys current
# 预期: Current key group: anthropic
```

**Step 3: 提交**

```bash
git add bin/vibe
git commit -m "feat: add keys subcommand to vibe dispatcher"
```

---

## Phase 3: 工具/MCP/Skill 管理

### Task 5: 实现 vibe tool 子命令

**Files:**
- Create: `bin/vibe-tool` - 工具管理入口
- Create: `lib/tool_manager.sh` - 工具管理库

**Step 1: 创建工具管理库**

```bash
#!/usr/bin/env zsh
# lib/tool_manager.sh

vibe_tool_list() {
    echo "Available tools:"

    local tools_dir="$VIBE_HOME/tools"

    if [[ ! -d "$tools_dir" ]]; then
        echo "  No tools configured"
        return
    fi

    for tool_dir in "$tools_dir"/*; do
        [[ -d "$tool_dir" ]] || continue
        local name="$(basename "$tool_dir")"
        local enabled="$([ -f "$tool_dir/enabled" ] && echo "enabled" || echo "disabled")"
        echo "  $name ($enabled)"
    done
}

vibe_tool_install() {
    local tool="$1"

    case "$tool" in
        claude)
            log_info "Installing Claude Code..."
            # 调用现有安装脚本
            ;;
        opencode)
            log_info "Installing OpenCode..."
            # 调用现有安装脚本
            ;;
        *)
            log_error "Unknown tool: $tool"
            return 1
            ;;
    esac
}

vibe_tool_enable() {
    local tool="$1"
    local tool_dir="$VIBE_HOME/tools/$tool"

    mkdir -p "$tool_dir"
    touch "$tool_dir/enabled"

    log_success "Enabled tool: $tool"
}

vibe_tool_disable() {
    local tool="$1"
    local tool_dir="$VIBE_HOME/tools/$tool"

    rm -f "$tool_dir/enabled"

    log_success "Disabled tool: $tool"
}
```

**Step 2: 创建 vibe-tool 命令入口**

```bash
#!/usr/bin/env zsh
# bin/vibe-tool

set -e

source "$(dirname "${(%):-%x}")/../lib/config.sh"
source "$(dirname "${(%):-%x}")/../lib/tool_manager.sh"

subcmd="${1:-}"
shift || true

case "$subcmd" in
    list)
        vibe_tool_list
        ;;
    install)
        vibe_tool_install "$@"
        ;;
    enable|on)
        vibe_tool_enable "$@"
        ;;
    disable|off)
        vibe_tool_disable "$@"
        ;;
    -h|--help)
        echo "Usage: vibe tool <command>"
        ;;
    *)
        echo "Unknown command: $subcmd"
        exit 1
        ;;
esac
```

**Step 3: 提交**

```bash
git add bin/vibe-tool lib/tool_manager.sh
git commit -m "feat: implement vibe tool command"
```

---

### Task 6: 实现 vibe mcp 和 vibe skill 子命令

**Files:**
- Create: `bin/vibe-mcp`
- Create: `bin/vibe-skill`
- Create: `lib/mcp_manager.sh`
- Create: `lib/skill_manager.sh`

这两个任务的实现模式与 vibe keys/tool 类似，使用简单的文件操作来管理 MCP 服务器和 Skills。

---

## Phase 4: 环境管理（init/export/doctor）

### Task 7: 实现 vibe init 和 vibe export

**Files:**
- Modify: `bin/vibe-init` - 添加新功能
- Create: `lib/env_manager.sh` - 环境管理库

**Step 1: 实现 vibe init**

```bash
# lib/env_manager.sh

vibe_init_interactive() {
    log_step "Initializing Vibe environment..."

    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"

    # 创建目录结构
    mkdir -p "$vibe_home"/{keys,tools,mcp,skills,cache}

    # 如果没有 vibe.yaml，创建默认配置
    if [[ ! -f "$vibe_home/vibe.yaml" ]]; then
        log_info "Creating default vibe.yaml..."
        cat > "$vibe_home/vibe.yaml" << 'EOF'
version: "1.0"
name: "vibe-env"

keys:
  current: anthropic

tools:
  claude:
    enabled: true
    default: true
  opencode:
    enabled: true

defaults:
  editor: cursor
  shell: zsh
EOF
    fi

    # 创建示例密钥文件
    if [[ ! -f "$vibe_home/keys/anthropic.env" ]]; then
        log_info "Creating sample keys file..."
        cat > "$vibe_home/keys/anthropic.env" << 'EOF'
# Anthropic API Keys
ANTHROPIC_AUTH_TOKEN=
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-5
EOF
    fi

    # 创建 current 符号链接
    if [[ ! -L "$vibe_home/keys/current" ]]; then
        ln -s anthropic.env "$vibe_home/keys/current"
    fi

    log_success "Vibe environment initialized at: $vibe_home"
    log_info "Run 'vibe keys set ANTHROPIC_AUTH_TOKEN=your-key' to set your API key"
}

vibe_export() {
    local output_file="${1:--}"

    if [[ "$output_file" == "-" ]]; then
        # 输出到 stdout（用于复制）
        cat "$VIBE_HOME/vibe.yaml"
        echo "---KEYS---"
        cat "$VIBE_HOME/keys/$(get_current_keys_group).env"
    else
        # 导出到文件
        tar -czf "$output_file" -C "$VIBE_HOME" .
        log_success "Exported to: $output_file"
    fi
}
```

**Step 2: 提交**

```bash
git add lib/env_manager.sh bin/vibe-init
git commit -m "feat: add vibe init and export functionality"
```

---

### Task 8: 实现 vibe doctor

**Files:**
- Modify: `bin/vibe-check` - 扩展诊断功能

**Step 1: 添加环境健康检查**

```bash
# 在 vibe-check 中添加环境检查

check_vibe_environment() {
    log_step "Checking Vibe environment..."

    local issues=0

    # 检查 VIBE_HOME
    if [[ -z "$VIBE_HOME" ]]; then
        log_error "VIBE_HOME not set"
        ((issues++))
    else
        log_info "VIBE_HOME: $VIBE_HOME"

        # 检查必要目录
        for dir in keys tools mcp skills; do
            if [[ -d "$VIBE_HOME/$dir" ]]; then
                log_info "  $dir/ - OK"
            else
                log_warn "  $dir/ - Not found"
            fi
        done

        # 检查当前密钥组
        local current_keys="$(get_current_keys_group)"
        log_info "Current keys: $current_keys"

        # 检查密钥文件
        local keys_file="$VIBE_HOME/keys/${current_keys}.env"
        if [[ -f "$keys_file" ]]; then
            # 检查是否有空密钥
            if grep -q "ANTHROPIC_AUTH_TOKEN=$" "$keys_file" 2>/dev/null; then
                log_warn "ANTHROPIC_AUTH_TOKEN is empty"
            fi
        fi
    fi

    if [[ $issues -eq 0 ]]; then
        log_success "Environment check passed"
    else
        log_warn "Found $issues issue(s)"
    fi
}
```

**Step 2: 提交**

```bash
git add bin/vibe-check
git commit -m "feat: add vibe doctor for environment health check"
```

---

## Phase 5: 智能交互（vibe chat 增强）

### Task 9: 实现 vibe chat 自然语言意图识别

**Files:**
- Modify: `bin/vibe-chat` - 添加意图识别
- Create: `lib/chat_router.sh` - 意图路由

**Step 1: 创建意图路由库**

```bash
#!/usr/bin/env zsh
# lib/chat_router.sh

# 意图映射表
declare -A INTENT_PATTERNS=(
    ["keys_use"]="切换|使用|切换到|改成|换到"
    ["keys_set"]="设置.*key|设置.*密钥|key.*设置"
    ["tool_install"]="安装|装一下|装个"
    ["tool_use"]="使用.*工具|切换.*工具|用.*工具"
    ["mcp_add"]="加.*mcp|添加.*mcp|配置.*mcp"
    ["init"]="初始化|开始|设置环境"
    ["export"]="导出|备份|导出配置"
)

route_intent() {
    local message="$1"

    # 检查每个意图模式
    for intent in "${(@k)INTENT_PATTERNS}"; do
        local pattern="${INTENT_PATTERNS[$intent]}"

        if [[ "$message" =~ $pattern ]]; then
            echo "$intent"
            return 0
        fi
    done

    # 未匹配，返回 chat
    echo "chat"
    return 1
}

handle_intent() {
    local intent="$1"
    local message="$2"

    case "$intent" in
        keys_use)
            # 提取提供商名称
            local provider
            provider=$(echo "$message" | grep -oE 'anthropic|openai|deepseek' | head -1)
            if [[ -n "$provider" ]]; then
                vibe_keys_use "$provider"
            else
                log_error "无法识别密钥提供商"
            fi
            ;;
        keys_set)
            # 提取 KEY=value
            local key_value
            key_value=$(echo "$message" | grep -oE '[A-Z_][A-Z0-9_]*=[^ ]+')
            if [[ -n "$key_value" ]]; then
                vibe_keys_set "$key_value"
            else
                log_error "无法识别密钥设置"
            fi
            ;;
        tool_install)
            # 提取工具名称
            local tool
            tool=$(echo "$message" | grep -oE 'claude|opencode|codex' | head -1)
            if [[ -n "$tool" ]]; then
                vibe_tool_install "$tool"
            else
                log_error "无法识别工具"
            fi
            ;;
        mcp_add)
            local mcp_name
            mcp_name=$(echo "$message" | grep -oE 'github|brave-search|filesystem' | head -1)
            if [[ -n "$mcp_name" ]]; then
                vibe_mcp_add "$mcp_name"
            else
                log_error "无法识别 MCP 服务"
            fi
            ;;
        init)
            vibe_init_interactive
            ;;
        export)
            vibe_export
            ;;
        chat|*)
            # 传递给 AI 处理
            return 1
            ;;
    esac
}
```

**Step 2: 更新 vibe-chat**

```bash
#!/usr/bin/env zsh
# bin/vibe-chat

source "$(dirname "${(%):-%x}")/../lib/config.sh"
source "$(dirname "${(%):-%x}")/../lib/keys_manager.sh"
source "$(dirname "${(%):-%x}")/../lib/tool_manager.sh"
source "$(dirname "${(%):-%x}")/../lib/mcp_manager.sh"
source "$(dirname "${(%):-%x}")/../lib/chat_router.sh"

# 获取消息
message="$*"

if [[ -z "$message" ]]; then
    echo "Usage: vibe chat <message>"
    exit 1
fi

# 尝试路由到 vibe 命令
if intent=$(route_intent "$message"); then
    if handle_intent "$intent" "$message"; then
        exit 0
    fi
fi

# 无法路由，调用 AI
log_info "Passing to AI assistant..."
exec claude "$message"
```

**Step 3: 提交**

```bash
git add bin/vibe-chat lib/chat_router.sh
git commit -m "feat: add natural language intent routing to vibe chat"
```

---

## Phase 6: 集成测试

### Task 10: 端到端测试

**Files:**
- Create: `tests/test_vibe_keys.sh`
- Create: `tests/test_vibe_chat_intent.sh`

**Step 1: 编写测试脚本**

```bash
#!/usr/bin/env zsh
# tests/test_vibe_keys.sh

set -e

export VIBE_HOME="/tmp/vibe-test-$$"
mkdir -p "$VIBE_HOME/keys"

# 创建测试密钥文件
echo "TEST_KEY=test-value" > "$VIBE_HOME/keys/anthropic.env"
echo "ANOTHER_KEY=another" > "$VIBE_HOME/keys/openai.env"
ln -s anthropic.env "$VIBE_HOME/keys/current"

# 测试 vibe keys list
echo "Testing vibe keys list..."
result=$(VIBE_HOME="$VIBE_HOME" bin/vibe keys list)
echo "$result" | grep -q "anthropic"

# 测试 vibe keys current
echo "Testing vibe keys current..."
result=$(VIBE_HOME="$VIBE_HOME" bin/vibe keys current)
echo "$result" | grep -q "Current key group: anthropic"

# 测试 vibe keys use
echo "Testing vibe keys use..."
VIBE_HOME="$VIBE_HOME" bin/vibe keys use openai
result=$(VIBE_HOME="$VIBE_HOME" bin/vibe keys current)
echo "$result" | grep -q "Current key group: openai"

# 清理
rm -rf "$VIBE_HOME"

echo "All tests passed!"
```

**Step 2: 运行测试**

```bash
zsh tests/test_vibe_keys.sh
```

**Step 3: 提交**

```bash
git add tests/test_vibe_keys.sh
git commit -m "test: add tests for vibe keys command"
```

---

## 实施顺序

```
Phase 1: 核心架构
├── Task 1: 目录结构模板
├── Task 2: vibe.yaml 解析器
│
Phase 2: 密钥管理
├── Task 3: vibe keys 实现
├── Task 4: 更新调度器
│
Phase 3: 工具管理
├── Task 5: vibe tool
├── Task 6: vibe mcp/skill
│
Phase 4: 环境管理
├── Task 7: vibe init/export
├── Task 8: vibe doctor
│
Phase 5: 智能交互
├── Task 9: vibe chat 意图识别
│
Phase 6: 测试
└── Task 10: 端到端测试
```

---

## 兼容性说明

- 现有别名（c, o, vibe flow 等）保持不变
- 新架构与旧配置可共存
- 渐进式迁移，先实现功能再废弃旧接口
