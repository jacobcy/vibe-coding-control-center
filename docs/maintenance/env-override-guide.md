# 环境变量覆盖维护指南

## 快速参考

**配置文件位置**: `src/vibe3/config/env_override.py`

**添加新环境变量覆盖只需一步**：更新 `OVERRIDE_RULES` 注册表

## 如何添加新的环境变量覆盖

### 步骤 1: 编辑 `src/vibe3/config/env_override.py`

在 `OVERRIDE_RULES` 列表中添加新规则：

```python
OVERRIDE_RULES: list[EnvOverrideRule] = [
    # ... 现有规则 ...
    
    # 添加新规则
    EnvOverrideRule(
        env_key="YOUR_ENV_VAR_NAME",              # 环境变量名
        config_path="section.subsection.field",    # 配置路径（点分隔）
        converter=str,                             # 类型转换函数
        description="简短描述此覆盖的用途",        # 文档说明
    ),
]
```

### 步骤 2: 测试验证（可选但推荐）

在 `tests/vibe3/config/test_env_override.py` 中添加测试：

```python
def test_your_new_override(self) -> None:
    """Test your new environment variable override."""
    config = {"section": {"subsection": {"field": "default_value"}}}
    
    with patch.dict(os.environ, {"YOUR_ENV_VAR_NAME": "new_value"}):
        result = apply_env_overrides(config)
    
    assert result["section"]["subsection"]["field"] == "new_value"
```

运行测试：
```bash
uv run pytest tests/vibe3/config/test_env_override.py::TestApplyEnvOverrides::test_your_new_override -v
```

**无需修改其他代码！** 框架自动处理：
- ✅ 配置加载时自动应用所有规则
- ✅ 类型转换和错误处理统一管理
- ✅ 日志记录和警告统一输出

## 类型转换示例

### 字符串（默认）
```python
EnvOverrideRule(
    env_key="MANAGER_USERNAMES",
    config_path="orchestra.manager_usernames",
    # converter=str 是默认值，可以省略
)
```

### 整数
```python
EnvOverrideRule(
    env_key="VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC",
    config_path="code_limits.total_file_loc.v2_shell",
    converter=int,
)
```

### 元组（逗号分隔）
```python
EnvOverrideRule(
    env_key="MANAGER_USERNAMES",
    config_path="orchestra.manager_usernames",
    converter=lambda s: tuple(s.split(",")),
)
```

### 列表
```python
EnvOverrideRule(
    env_key="ALLOWED_BRANCHES",
    config_path="flow.protected_branches",
    converter=lambda s: s.split(","),
)
```

### 布尔值
```python
EnvOverrideRule(
    env_key="ENABLE_DEBUG_MODE",
    config_path="orchestra.debug",
    converter=lambda s: s.lower() in ("true", "1", "yes"),
)
```

### 复杂类型（JSON）
```python
import json

EnvOverrideRule(
    env_key="CUSTOM_CONFIG",
    config_path="custom.settings",
    converter=json.loads,
)
```

## 配置路径说明

配置路径使用点分隔符，对应 YAML 配置的嵌套结构：

**YAML 配置**：
```yaml
# config/v3/settings.yaml
orchestra:
  manager_usernames:
    - "vibe-manager-agent"
```

**对应配置路径**：
```python
config_path="orchestra.manager_usernames"
```

**嵌套示例**：
```yaml
code_limits:
  total_file_loc:
    v2_shell: 4000
```

**对应配置路径**：
```python
config_path="code_limits.total_file_loc.v2_shell"
```

## 常见问题

### Q: 如何验证环境变量已生效？

**A**: 检查日志输出：
```bash
# 启动时查看日志
vibe3 serve start 2>&1 | grep "Applied env override"

# 输出示例
2026-06-03 11:15:57 | DEBUG | vibe3.config.env_override:apply_env_overrides:172 - Applied env override: MANAGER_USERNAMES -> orchestra.manager_usernames
```

### Q: 环境变量优先级是什么？

**A**: 优先级从高到低：
1. **环境变量**（最高）
2. YAML 配置文件
3. 代码默认值（最低）

### Q: 如何查看所有支持的环境变量？

**A**: 查看 `OVERRIDE_RULES` 注册表：
```python
from vibe3.config.env_override import OVERRIDE_RULES

for rule in OVERRIDE_RULES:
    print(f"{rule.env_key:40} -> {rule.config_path:40} ({rule.description})")
```

### Q: 可以临时禁用某个环境变量覆盖吗？

**A**: 可以，有两种方式：

1. **注释掉规则**：
```python
OVERRIDE_RULES = [
    # EnvOverrideRule(env_key="TEMP_DISABLE", config_path="..."),
]
```

2. **取消设置环境变量**：
```bash
unset MANAGER_USERNAMES
vibe3 serve start
```

### Q: 如何处理无效的环境变量值？

**A**: 框架自动处理：
- 无效值记录警告日志
- 保持配置文件中的默认值
- 不会崩溃或抛出异常

**日志示例**：
```
2026-06-03 11:15:57 | WARNING | vibe3.config.env_override:apply_env_overrides:179 - Invalid env value for VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC: 'invalid', error: invalid literal for int() with base 10: 'invalid'
```

## 实际案例

### 案例 1: 添加新的 manager usernames 覆盖

**需求**: 允许通过环境变量 `MANAGER_USERNAMES` 覆盖 manager 用户名列表。

**实现**:
```python
EnvOverrideRule(
    env_key="MANAGER_USERNAMES",
    config_path="orchestra.manager_usernames",
    converter=lambda s: tuple(s.split(",")),
    description="Comma-separated list of manager GitHub usernames",
),
```

**使用**:
```bash
export MANAGER_USERNAMES=manager1,manager2,manager3
vibe3 serve start
```

### 案例 2: 添加代码行数限制覆盖

**需求**: 允许通过环境变量调整代码行数限制。

**实现**:
```python
EnvOverrideRule(
    env_key="VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC",
    config_path="code_limits.total_file_loc.v2_shell",
    converter=int,
    description="Total lines of code limit for V2 shell scripts",
),
```

**使用**:
```bash
export VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC=5000
vibe3 check
```

### 案例 3: 添加测试覆盖率要求覆盖

**需求**: 允许在 CI 中动态调整测试覆盖率要求。

**实现**:
```python
EnvOverrideRule(
    env_key="VIBE_TEST_COVERAGE_SERVICES",
    config_path="quality.test_coverage.services",
    converter=int,
    description="Test coverage requirement for services layer",
),
```

**使用**:
```bash
export VIBE_TEST_COVERAGE_SERVICES=90
uv run pytest --cov
```

## 维护检查清单

添加新环境变量覆盖时，确保：

- [ ] 在 `OVERRIDE_RULES` 中添加新规则
- [ ] 正确设置 `env_key`（环境变量名）
- [ ] 正确设置 `config_path`（配置路径）
- [ ] 选择合适的 `converter` 函数
- [ ] 添加 `description` 文档说明
- [ ] （可选）添加单元测试验证
- [ ] （可选）更新用户文档

## 相关文档

- **实现文档**: `temp/env-override-implementation.md`
- **测试文件**: `tests/vibe3/config/test_env_override.py`
- **源代码**: `src/vibe3/config/env_override.py`
- **使用示例**: `src/vibe3/services/orchestra_helpers.py`

---

**维护者**: Vibe Team  
**最后更新**: 2026-06-03  
**PR**: #1941
