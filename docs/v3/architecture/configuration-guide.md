# Vibe Center 配置系统

## 配置真源原则

**config/settings.yaml 是唯一配置真源**。

### 设计原则

1. **单一真源**：所有配置值都从 `config/settings.yaml` 读取
2. **最小安全默认值**：Pydantic 模型提供宽松的默认值，仅用于降级场景
3. **类型安全**：Pydantic 模型提供类型检查和验证

### 使用方式

#### 标准方式（推荐）

```python
from vibe3.config.loader import get_config

config = get_config()
print(config.code_limits.v3_python.total_loc)  # 从 YAML 读取
```

#### 直接从默认配置读取

```python
from vibe3.config.settings import VibeConfig

config = VibeConfig.get_defaults()  # 从 config/settings.yaml 读取
```

#### 从自定义路径读取

```python
from vibe3.config.settings import VibeConfig
from pathlib import Path

config = VibeConfig.from_yaml(Path("custom/config.yaml"))
```

### 配置加载顺序

`get_config()` 按以下顺序查找配置文件：

1. `.vibe/config.yaml` - 项目特定配置
2. `config/settings.yaml` - 默认配置（推荐）
3. `~/.vibe/config.yaml` - 全局配置
4. Pydantic 最小安全默认值 - 降级场景

### 修改配置

编辑 `config/settings.yaml`：

```yaml
code_limits:
  v3_python:
    total_loc: 9000
    max_file_loc: 300
    min_tests: 5
    test_file_loc:
      services: 180
      clients: 200
      commands: 120
```

### 环境变量覆盖

可以通过环境变量覆盖配置：

```bash
export VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC=10000
export VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC=8000
export VIBE_TEST_COVERAGE_SERVICES=85
```

### 最小安全默认值

如果 YAML 文件不存在，系统使用宽松的默认值：

- `total_loc: 10000` - 代码总量限制
- `max_file_loc: 500` - 单文件行数限制
- `test_file_loc.services: 500` - 测试文件行数限制

这些默认值故意设置得比较宽松，避免阻止正常开发。**生产环境应该使用 `config/settings.yaml`**。

### 注意事项

1. **不要在代码中硬编码配置值**
2. **所有测试都应该使用 `get_config()` 读取配置**
3. **修改配置后重启应用或调用 `reload_config()`**