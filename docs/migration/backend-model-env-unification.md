# Backend/Model 环境变量命名统一 - 迁移说明

## 变更内容

### 删除的旧命名

**旧命名（已弃用）**：
- `VIBE3_MANAGER_BACKEND`
- `VIBE3_MANAGER_MODEL`

**位置**：`src/vibe3/roles/manager.py`

### 统一的新命名

**新命名（统一使用）**：
- `VIBE_BACKEND_MANAGER`
- `VIBE_MODEL_MANAGER`
- `VIBE_BACKEND_GOVERNANCE`
- `VIBE_MODEL_GOVERNANCE`
- `VIBE_BACKEND_SUPERVISOR`
- `VIBE_MODEL_SUPERVISOR`
- `VIBE_BACKEND_PLANNER`
- `VIBE_MODEL_PLANNER`
- `VIBE_BACKEND_EXECUTOR`
- `VIBE_MODEL_EXECUTOR`
- `VIBE_BACKEND_REVIEWER`
- `VIBE_MODEL_REVIEWER`

**位置**：`src/vibe3/config/env_override.py`

## 迁移操作

### 代码变更

**删除**：`src/vibe3/roles/manager.py`
- 第 58-66 行：删除旧命名环境变量读取
- 第 208-216 行：删除旧命名环境变量注入

**说明**：
- Backend/model 覆盖已在配置加载时由 `env_override.py` 处理
- 不需要在运行时再次检查或注入环境变量

### Keys.env 配置

**用户操作**：

如果您的 `config/keys.env` 中有旧命名：
```bash
# ❌ 旧命名（已弃用）
VIBE3_MANAGER_BACKEND=claude
VIBE3_MANAGER_MODEL=sonnet
```

请更新为新命名：
```bash
# ✅ 新命名（统一使用）
VIBE_BACKEND_MANAGER=claude
VIBE_MODEL_MANAGER=sonnet
```

### 完整示例

```bash
# config/keys.env

# ================= Agent 配置覆盖（可选） =================
# 通过环境变量覆盖 config/v3/settings.yaml 中的 agent 配置
# 格式：VIBE_BACKEND_<ROLE> / VIBE_MODEL_<ROLE>
# Role 名称：manager, governance, supervisor, planner, executor, reviewer

# Manager agent
VIBE_BACKEND_MANAGER=claude
VIBE_MODEL_MANAGER=sonnet

# Governance agent
VIBE_BACKEND_GOVERNANCE=codex
VIBE_MODEL_GOVERNANCE=gpt-5.4

# Supervisor agent
VIBE_BACKEND_SUPERVISOR=gemini
VIBE_MODEL_SUPERVISOR=gemini-3-flash-preview

# 注意：所有配置覆盖统一由 src/vibe3/config/env_override.py 管理
# 完整列表见该文件的 OVERRIDE_RULES
```

## 覆盖机制说明

### 配置覆盖流程

```
用户设置环境变量（keys.env）
  ↓
lib3/vibe.sh 加载 keys.env
  ↓
export 环境变量到进程
  ↓
Python CLI 加载配置
  ↓
env_override.py::apply_env_overrides()
  ↓
环境变量覆盖到 config 字段
  ↓
配置生效
```

### 优先级

从高到低：
1. **环境变量**（最高）- `VIBE_BACKEND_MANAGER` 等
2. **YAML 配置** - `config/v3/settings.yaml`
3. **代码默认值**（最低）

## 影响范围

### 不受影响

**已经使用新命名的用户**：
- 无需任何修改
- 配置继续正常工作

**没有使用环境变量覆盖的用户**：
- 无需任何操作
- 使用 YAML 配置文件即可

### 需要迁移

**使用旧命名的用户**：
- 更新 `keys.env` 或 `.zshrc` 中的环境变量名
- 从 `VIBE3_MANAGER_BACKEND` 改为 `VIBE_BACKEND_MANAGER`
- 从 `VIBE3_MANAGER_MODEL` 改为 `VIBE_MODEL_MANAGER`

## 其他 Role 的覆盖

按照相同模式添加到 `keys.env`：

```bash
# Planner
VIBE_BACKEND_PLANNER=opencode
VIBE_MODEL_PLANNER=deepseek/deepseek-v4-pro

# Executor
VIBE_BACKEND_EXECUTOR=gemini
VIBE_MODEL_EXECUTOR=gemini-3-flash-preview

# Reviewer
VIBE_BACKEND_REVIEWER=claude
VIBE_MODEL_REVIEWER=sonnet
```

**注意**：所有覆盖必须添加到 `env_override.py` 的 `OVERRIDE_RULES` 才会生效。

如需添加新的 role 覆盖，请参考：`docs/maintenance/env-override-guide.md`

## 验证方法

### 检查环境变量生效

启动 orchestra 并查看日志：

```bash
vibe3 serve start 2>&1 | grep "Applied env override"
```

**输出示例**：
```
2026-06-03 11:15:57 | DEBUG | vibe3.config.env_override - Applied env override: VIBE_BACKEND_MANAGER -> orchestra.assignee_dispatch.backend
```

### 验证 manager 使用正确 backend

```bash
vibe3 serve status
```

查看 Manager 配置行，确认 backend/model 正确。

## 参考文档

- **实现文档**: `src/vibe3/config/env_override.py`
- **维护指南**: `docs/maintenance/env-override-guide.md`
- **现状分析**: `temp/env-var-analysis.md`

---

**维护者**: Vibe Team  
**最后更新**: 2026-06-03  
**相关 PR**: #1941