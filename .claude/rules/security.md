---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

## Secret Management

本项目使用 **direnv** 管理环境变量（不使用 python-dotenv）。

**项目特定选择**:
- 使用 `direnv` 自动加载 `.envrc` 文件中的环境变量
- 全局 Python 规则推荐使用 `python-dotenv`，但本项目使用 `direnv` 实现更通用的环境变量管理
- 该选择适用于 Shell + Python 混合项目

```bash
# .envrc 文件（项目根目录）
export GH_TOKEN="ghp_xxx"
export OPENAI_API_KEY="sk-xxx"
```

在 Python 中访问环境变量：

```python
import os

api_key = os.environ["OPENAI_API_KEY"]  # Raises KeyError if missing
```

## Security Scanning

- 运行 **pre-commit** 进行自动检查（包含 ruff、black、mypy）：
  ```bash
  pre-commit run --all-files
  ```

## Reference

See skill: `django-security` for Django-specific security guidelines (if applicable).
