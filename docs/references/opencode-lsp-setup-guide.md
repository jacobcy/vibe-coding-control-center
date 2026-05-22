---
document_type: reference
title: OpenCode LSP 配置指南
status: verified
scope: external-tool-integration
author: Sisyphus Agent
created: 2026-05-22
last_updated: 2026-05-22
related_docs:
  - oh-my-opencode-guide.md
  - DEVELOPER.md
verified_platforms:
  - macOS (darwin)
  - npm 11.10.1
  - node v22.22.0
---

# OpenCode LSP 配置指南

> **验证日期**：2026-05-22
> **验证环境**：macOS Darwin, npm 11.10.1, node v22.22.0
> **参考来源**：https://www.cnblogs.com/zer0Black/p/19687384

## 概述

LSP (Language Server Protocol) 为 OpenCode 提供代码补全、类型检查、重构等能力。本文档介绍如何在 macOS/Linux 环境下配置 TypeScript、Python、YAML 三种常用语言的 LSP Server。

**验证结论**：经过实际测试，TypeScript、Python、YAML LSP 均已成功配置并在 OpenCode 中生效。

## 快速安装

### 一键安装命令

```bash
npm install -g typescript typescript-language-server pyright yaml-language-server
```

### 安装后验证

```bash
# 检查安装版本
typescript-language-server --version  # 期望输出: 5.3.0+
pyright --version                     # 期望输出: 1.1.408+
yaml-language-server --version        # 期望输出: 1.23.0+
tsc --version                         # 期望输出: 5.x+
```

## 详细说明

### TypeScript LSP

**组件**：`typescript` + `typescript-language-server`

**安装**：
```bash
npm install -g typescript typescript-language-server
```

**验证测试**：
```bash
# 创建测试文件
cat > /tmp/test.ts << 'EOF'
const x: string = "hello";
const y: number = x; // Type error
EOF

# 使用 OpenCode lsp_diagnostics 工具检查
# 期望输出: error[typescript] (2322) at 2:6: Type 'string' is not assignable to type 'number'.
```

**注意事项**：
- TypeScript LSP 需要项目中安装 TypeScript 依赖，或全局安装 `typescript` 包
- 如果遇到 "Could not find a valid TypeScript installation" 错误，请确保 `tsc` 命令可用

### Python LSP

**组件**：`pyright`

**安装**：
```bash
npm install -g pyright
```

**验证测试**：
```bash
# OpenCode 已内置 Python LSP 支持
# 对任意 Python 文件运行 lsp_diagnostics 即可验证
# 示例输出: error[Pyright] (reportPrivateImportUsage) at 41:25: "Panel" is not exported...
```

**注意事项**：
- Pyright 是 Microsoft 开发的 Python 静态类型检查器
- 支持 Python 3.8+ 语法
- 配置文件：`pyrightconfig.json` 或 `pyproject.toml`

### YAML LSP

**组件**：`yaml-language-server`

**安装**：
```bash
npm install -g yaml-language-server
```

**验证测试**：
```bash
# 创建测试文件
cat > /tmp/test.yaml << 'EOF'
key1: value1
key2:
  - item1
  - item2
invalid: [unclosed
EOF

# 使用 OpenCode lsp_diagnostics 工具检查
# 期望输出: error[YAML] at 6:0: Flow sequence in block collection must be sufficiently indented...
```

**注意事项**：
- YAML LSP 支持 YAML Schema 验证
- 支持常见的 YAML 格式化功能

## 配置文件说明

### OpenCode 内置配置

OpenCode 已经内置了主流 LSP Server 的配置，无需手动编辑配置文件。安装 LSP Server 后，OpenCode 会自动识别并使用。

**内置支持的 LSP Server**（部分列表）：
- `typescript` - TypeScript/JavaScript
- `deno` - Deno TypeScript
- `vue` - Vue.js
- `eslint` - ESLint
- `oxlint` - Oxlint
- `biome` - Biome (需单独安装)
- `gopls` - Go
- `ruby-lsp` - Ruby
- `basedpyright` - Python (pyright fork)
- `pyright` - Python

### 可选：手动配置

如果需要自定义 LSP Server 配置，可以在 `~/.config/opencode/oh-my-opencode.json` 中添加 `lsp` 字段：

```json
{
  "lsp": {
    "typescript-language-server": {
      "command": ["typescript-language-server", "--stdio"],
      "extensions": [".ts", ".tsx"],
      "priority": 10,
      "env": { "NODE_OPTIONS": "--max-old-space-size=4096" },
      "initialization": {
        "preferences": { "includeInlayParameterNameHints": "all" }
      }
    },
    "pyright": {
      "command": ["pyright-langserver", "--stdio"],
      "extensions": [".py", ".pyi"],
      "priority": 10,
      "env": { "NODE_OPTIONS": "--max-old-space-size=4096" },
      "initialization": {
        "preferences": {
          "python": {
            "analysis": {
              "typeCheckingMode": "basic",
              "autoSearchPaths": true,
              "useLibraryCodeForTypes": true
            }
          }
        }
      }
    },
    "yaml-language-server": {
      "command": ["yaml-language-server", "--stdio"],
      "extensions": [".yaml", ".yml"],
      "priority": 10,
      "initialization": {
        "yaml": {
          "format": { "enable": true },
          "validate": true,
          "hover": true,
          "completion": true
        }
      }
    }
  }
}
```

## 故障排除

### 问题：command not found: typescript-language-server

**原因**：npm 全局安装目录不在 PATH 中

**解决方案**：
```bash
# 检查 npm 全局路径
npm config get prefix

# 将其 bin 子目录添加到 PATH
# 假设输出为 /usr/local，则添加：
export PATH="/usr/local/bin:$PATH"

# 永久生效（添加到 ~/.zshrc 或 ~/.bashrc）
echo 'export PATH="$(npm config get prefix)/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 问题：TypeScript LSP 报错 "Could not find a valid TypeScript installation"

**原因**：缺少 TypeScript 编译器

**解决方案**：
```bash
npm install -g typescript
```

### 问题：LSP 不生效

**排查步骤**：
1. 检查 LSP Server 是否正确安装（运行版本命令）
2. 检查 npm 全局 bin 目录是否在 PATH 中
3. 重启 OpenCode
4. 检查文件扩展名是否匹配（如 `.ts`、`.py`、`.yaml`）

### 问题：Python LSP 误报

**原因**：Pyright 的类型检查可能比 mypy 更严格

**解决方案**：
- 在项目根目录创建 `pyrightconfig.json` 调整检查级别
- 或在 `pyproject.toml` 中添加 `[tool.pyright]` 配置

## 验证清单

完成安装后，按以下清单验证：

- [ ] `typescript-language-server --version` 输出版本号
- [ ] `pyright --version` 输出版本号
- [ ] `yaml-language-server --version` 输出版本号
- [ ] `tsc --version` 输出版本号（TypeScript 编译器）
- [ ] 在 `.ts` 文件上运行 `lsp_diagnostics`，成功检测类型错误
- [ ] 在 `.py` 文件上运行 `lsp_diagnostics`，成功检测导入/类型错误
- [ ] 在 `.yaml` 文件上运行 `lsp_diagnostics`，成功检测语法错误

## 相关资源

- **参考博客**：https://www.cnblogs.com/zer0Black/p/19687384
- **TypeScript LSP**：https://github.com/typescript-language-server/typescript-language-server
- **Pyright**：https://github.com/microsoft/pyright
- **YAML LSP**：https://github.com/redhat-developer/yaml-language-server
- **LSP 规范**：https://microsoft.github.io/language-server-protocol/

## 附录：Java LSP 说明

Java LSP (jdtls) 配置较为复杂，需要从 Eclipse 官方下载并配置 PATH。本文档未包含 Java LSP 配置，如有需要请参考原始博客文章。

**原因**：
- jdtls 需要手动下载 tar.gz 并解压
- PATH 配置容易出错（需指向正确的 bin 目录）
- 安装过程涉及网络访问（Eclipse 服务器）

如需配置 Java LSP，请参考：
https://www.cnblogs.com/zer0Black/p/19687384
