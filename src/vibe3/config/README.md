# Config

配置加载与 schema 验证层,从 YAML 文件加载配置并通过 Pydantic 验证。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| settings.py | 289 | 主配置 schema（VibeConfig）、orchestra 子配置 |
| loader.py | 185 | YAML 加载逻辑、配置文件解析 |
| settings_pr.py | 85 | PR quality gate 子配置 |
| get.py | 74 | 全局配置访问入口（get_config） |
| __init__.py | 31 | 公共 API 导出 |
| orchestra_settings.py | 12 | Orchestra 配置辅助（动态修改配置） |

**总计**: 6 文件,676 行代码

## 架构说明

Config 模块采用分层配置架构,将配置分为根配置和子配置域。

### 配置层次结构

```
VibeConfig (根配置)
├── orchestra: OrchestraConfig (from models.orchestra_config)
│   ├── managers: dict[str, ManagerConfig]
│   ├── default_manager: str
│   └── async_execution: bool
├── code_limits: CodeLimitsConfig
│   ├── single_file_loc: int (default: 500)
│   └── total_file_loc: int (default: 3000)
├── code_paths: CodePathsConfig
│   └── exclude: list[str]
├── test_paths: TestPathsConfig
│   └── test_dirs: list[str]
├── review_scope: ReviewScopeConfig
│   └── max_files: int
├── quality: QualityConfig
│   └── merge_gate: MergeGateConfig
│       ├── tests: str
│       ├── mypy: str
│       └── ruff: str
└── pr_scoring: PRScoringConfig (from settings_pr)
    ├── high_risk_file_patterns: list[str]
    ├── critical_paths: list[str]
    └── penalty_thresholds: dict
```

### 加载流程

```
config/settings.yaml
       ↓
   loader.py (load_config)
       ↓
   settings.py (VibeConfig 验证)
       ↓
   get.py (get_config 缓存)
```

### 设计原则

- **单一职责**: `loader.py` 只负责加载,`settings.py` 只定义 schema
- **类型安全**: 所有配置通过 Pydantic BaseModel 验证
- **懒加载**: 配置在首次访问时加载,后续通过 `get_config()` 缓存
- **分离关注点**: PR scoring 配置独立为 `settings_pr.py`

## 内部依赖

```
config/
├── loader.py → settings.py (VibeConfig)
├── settings.py → settings_pr.py (PRScoringConfig)
├── settings.py → models.orchestra_config (OrchestraConfig)
├── get.py → loader.py (load_config)
├── orchestra_settings.py → settings.py (VibeConfig)
└── orchestra_settings.py → models.orchestra_config (OrchestraConfig)
```

**循环依赖检查**: ✅ 无循环依赖

**跨模块依赖**:
- `settings.py` 和 `orchestra_settings.py` 都依赖 `models.orchestra_config`
- 这是为了让 orchestra 配置可以在 models 层定义（数据模型）并在 config 层使用

## 公共 API

`__init__.py` 导出以下接口：

**配置加载**:
- `get_config()` - 获取全局配置实例（带缓存）
- `load_config()` - 从文件加载配置
- `reload_config()` - 强制重新加载配置

**配置模型**:
- `VibeConfig` - 根配置
- `CodeLimitsConfig` - 代码限制配置
- `SingleFileLocConfig` - 单文件行数限制
- `TotalFileLocConfig` - 总行数限制
- `CodePathsConfig` - 代码路径配置
- `TestPathsConfig` - 测试路径配置
- `ReviewScopeConfig` - Review 范围配置
- `QualityConfig` - 质量配置
- `PRScoringConfig` - PR 评分配置
- `MergeGateConfig` - Merge 门控配置

## 外部依赖

- **models/**: `models.orchestra_config` (OrchestraConfig)
- **exceptions/**: ConfigError

## 被依赖

- **几乎所有模块**: 通过 `get_config()` 访问配置
- **commands/**: 使用配置控制行为
- **services/**: 使用配置初始化服务
- **agents/**: 使用配置准备 prompt