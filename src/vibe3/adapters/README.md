# Adapters

适配器层，声明式资源分发，支持 vibe-center 和 github-flow 两种发行版。

## 职责

- Adapter 注册表：延迟加载、注册、查询、列表接口
- VibeCenter 适配器：从仓库资源构建 manifest（policies、supervisors、skills、workflows）
- GitHub Flow 适配器：轻量 global skills 发行版
- Resource Root 解析：marker-based 资源根路径解析

## 文件列表

统计时间：2026-06-27

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 68 | Adapter 注册表（注册、查询、延迟加载） |
| vibe_center.py | 151 | VibeCenter 适配器 manifest 构建 |
| github_flow.py | 36 | GitHub Flow 适配器 manifest 构建 |
| resource_root.py | 63 | Resource root 解析（marker-based） |

**总计**：4 文件，328 行

## 公共 API

从 `__init__.py` 的 `__all__` 导出的 2 个符号：

- `register_adapter(manifest)` — 注册 adapter manifest
- `get_adapter(name)` — 获取 adapter（支持 lazy loading）

注：`resource_root.py` 的 `resolve_resource_root()` 和 `ResourceRootNotFoundError` 为内部实现，未从 `adapters` 重导出。

## 架构说明

### Adapter Registry

`__init__.py` 实现延迟加载的 adapter 注册表：

- `_ADAPTERS: dict[str, AdapterManifest]` — 已注册 adapter manifest
- `_LOADED: set[str]` — 已加载 adapter 名称（避免重复构建）
- `get_adapter(name)` 首次访问时自动加载并构建内置 adapter

### VibeCenter Adapter

`vibe_center.py` 从仓库资源构建 VibeCenter 发行版 manifest：

- **资源扫描**：policies、supervisors、skills、workflows
- **动态发现**：扫描 `skills/` 目录下的所有子目录（包含 SKILL.md）
- **路径解析**：使用 `resolve_resource_root()` 查找包含 `skills` marker 的根
- **依赖注入**：接受 `git_common_dir` 和 `global_skills` 参数

### GitHub Flow Adapter

`github_flow.py` 提供轻量级 skills 发行版：

- **资源来源**：仅从 `global_skills` 目录扫描
- **无本地依赖**：不依赖仓库根目录，适合 global runtime 使用

### Resource Root Resolution

`resource_root.py` 提供基于 marker 的资源根解析：

- **候选路径**：git common dir parent、additional_roots、cwd 及其 parents
- **Marker 验证**：检查候选路径是否包含 required_marker
- **路径去重**：使用 `seen: set[Path]` 避免重复检查
- **异常处理**：无法解析时抛出 `ResourceRootNotFoundError`

## 依赖关系

### 内部依赖

```
adapters/
├── __init__.py → vibe3.clients (GitClient, runtime_assets_root)
│               → vibe3.models (AdapterManifest)
│               → vibe_center.py, github_flow.py (lazy import)
├── vibe_center.py → resource_root.py (resolve_resource_root)
│                  → vibe3.models (AdapterManifest, AdapterResource)
├── github_flow.py → vibe3.models (AdapterManifest, AdapterResource)
└── resource_root.py → (无内部依赖，纯 pathlib)
```

### 外部依赖

- `clients`：GitClient（获取 git common dir）、runtime_assets_root（全局资源路径）
- `models`：AdapterManifest、AdapterResource（adapter manifest 定义）

### 被依赖

- `commands`：CLI 命令查询可用 adapter
- `orchestra`：全局编排加载 adapter manifest
- `server`：Server 启动时初始化 adapter

## 设计原则

1. **延迟加载**：adapter manifest 首次访问时才构建，避免启动时全量扫描
2. **Marker-based 解析**：使用目录/文件标记（如 `skills`）定位资源根，不依赖硬编码路径
3. **声明式 manifest**：adapter 通过 AdapterManifest 描述资源列表，不暴露具体文件路径
4. **可扩展发行版**：支持注册新 adapter，实现不同资源分发策略