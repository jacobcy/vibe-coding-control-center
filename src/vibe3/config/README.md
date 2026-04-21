# Config

配置加载与 schema 验证层，从 YAML 文件加载配置并通过 Pydantic 验证。

## 职责

- 加载 config/settings.yaml 配置文件
- Pydantic schema 验证和类型安全
- 运行时配置访问 (get_config/reload_config)
- 子配置域：Orchestra, PR, AI, Code Limits

## 关键组件

| 文件 | 职责 |
|------|------|
| settings.py | 主配置 schema (VibeConfig) |
| settings.py | 根配置与 orchestra 子配置 |
| settings_pr.py | PR quality gate 子配置 |
| loader.py | YAML 加载逻辑 |
| get.py | 全局配置访问入口 |

## 注意

配置 YAML 文件位于仓库根目录 `config/settings.yaml`，不在 `src/vibe3/config/` 下。
本模块（`src/vibe3/config/`）负责**加载和验证**，不存储配置文件本身。

## 依赖关系

- 依赖: (无内部依赖，读取仓库根 config/settings.yaml)
- 被依赖: 几乎所有模块
