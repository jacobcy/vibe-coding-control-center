# Plan: AI 文本辅助集成

**目标**: 为 `vibe3 pr create --ai` 提供轻量 AI 文案辅助（`flow new --ai` 已移除），生成符合格式的文本。

**原则**:
- 最小实现，不过度设计
- 模块化，便于扩展
- 优雅降级，不阻塞用户

---

## 一、核心设计

### 1.1 架构分层

```
Commands (CLI 接口)
    ↓
Services (业务逻辑)
    ↓
Clients (外部 API)
```

**新增模块**:
- `src/vibe3/clients/ai_client.py` - AI API 客户端（单一职责：调用 API）
- `src/vibe3/services/ai_service.py` - AI 服务（单一职责：业务逻辑）

**修改模块**:
- （已取消）`src/vibe3/commands/flow.py` - 早期设计的 `--ai` 入口已废弃
- `src/vibe3/commands/pr_create.py` - 添加 `--ai` 选项

### 1.2 配置设计

**分离关注点**:
- `config/settings.yaml` → AI 系统配置（enabled, provider, model）
- `config/prompts.yaml` → Prompts 模板（用户可自定义）

**理由**:
- 配置很少变，prompts 可能频繁调整
- 用户可以只修改 prompts，不影响系统配置
- 未来可以支持多个 prompt 文件

### 1.3 依赖选择

**使用 `openai` 官方库**

**理由**:
- 稳定可靠，官方维护
- 通过 `base_url` 支持 OpenAI 兼容 API（Ollama、vLLM、本地模型）
- 类型支持好，符合项目标准

**兼容性**:
```python
# OpenAI
client = OpenAI(api_key="...")

# Ollama
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# vLLM
client = OpenAI(base_url="http://localhost:8000/v1", api_key="vllm")
```

---

## 二、模块设计

### 2.1 AI Client (`clients/ai_client.py`)

**职责**: 封装 OpenAI API 调用，支持多后端

**核心方法**:
```python
class AIClient:
    def __init__(self, config: dict) -> None: ...

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> str | None:
        """生成文本，失败返回 None（优雅降级）"""
```

**错误处理**:
- API 调用失败 → 记录日志，返回 None
- 超时 → 返回 None
- 不抛出异常，让调用者无感知

### 2.2 AI Service (`services/ai_service.py`)

**职责**: 提供业务级 API

**核心方法**:
```python
class AIService:
    def suggest_flow_slug(
        self,
        issue_title: str,
        issue_body: str | None = None
    ) -> list[str] | None:
        """返回建议列表或 None"""

    def suggest_pr_content(
        self,
        commits: list[str],
        changed_files: list[str] | None = None
    ) -> tuple[str, str] | None:
        """返回 (title, body) 或 None"""
```

**Prompt 加载**:
- 从 `config/prompts.yaml` 加载模板
- 支持变量替换（`{issue_title}`, `{commits}` 等）

### 2.3 Prompts 配置 (`config/prompts.yaml`)

```yaml
flow:
  slug_suggestion:
    system: |
      You are an assistant that generates concise flow slugs...
    user: |
      Issue: {issue_title}

      Generate 3 flow slug suggestions (kebab-case)...

pr:
  title_suggestion:
    system: |
      You are an assistant that generates PR titles...
    user: |
      Commits:
      {commits}

      Generate a PR title...
  body_suggestion:
    system: |
      You are an assistant that generates PR descriptions...
    user: |
      Commits:
      {commits}

      Generate a PR body...
```

### 2.4 系统配置 (`config/settings.yaml`)

```yaml
ai:
  enabled: false              # 总开关
  provider: "openai"          # openai, anthropic, ollama
  api_key_env: "OPENAI_API_KEY"
  base_url: null              # 可选：自定义 API endpoint
  model: "gpt-4o-mini"        # 模型名称
  timeout: 30                 # 超时秒数
```

---

## 三、实现步骤（TDD）

### Phase 1: 基础设施

**步骤**:
1. 添加 `openai` 依赖到 `pyproject.toml`
2. 扩展 `settings.yaml` 添加 AI 配置
3. 创建 `config/prompts.yaml` 文件
4. 在 `config/settings.py` 添加 `AIConfig` 模型

**验证**:
- 配置能正确加载
- Prompts 能正确读取

### Phase 2: Client 层

**步骤**:
1. 创建 `clients/ai_client.py`
2. 实现 `AIClient` 类
3. 编写单元测试

**测试要点**:
- 正常调用
- API 密钥缺失
- 超时处理
- 自定义 base_url

### Phase 3: Service 层

**步骤**:
1. 创建 `services/ai_service.py`
2. 实现 `AIService` 类
3. 加载 prompts 配置
4. 编写单元测试

**测试要点**:
- flow slug 生成
- PR 内容生成
- AI 禁用时的行为
- prompt 模板渲染

### Phase 4: Command 层集成

**步骤**:
1. （已取消）保留 flow 手动输入，不再添加 `--ai` 选项
2. 修改 `commands/pr_create.py` 添加 `--ai` 选项
3. 编写集成测试

**行为**:
```bash
# pr create
vibe3 pr create --ai
# → AI 生成 title 和 body，用户确认或编辑

# flow new --ai 已移除
```

**降级逻辑**:
- AI 禁用 → 正常流程（无提示）
- AI 调用失败 → 提示用户，回退到手动输入

---

## 四、错误处理

### 4.1 异常策略

**原则**: 不抛出异常，优雅降级

```python
# ❌ 错误做法
def suggest_flow_slug(...):
    if not self.ai_enabled:
        raise AIDisabledError()
    ...

# ✅ 正确做法
def suggest_flow_slug(...):
    if not self.ai_enabled:
        return None
    ...
```

### 4.2 日志记录

```python
# AI 禁用
logger.debug("AI assistance disabled in config")

# API 调用失败
logger.warning(f"AI API call failed: {error}")

# 降级
logger.info("Falling back to manual input")
```

### 4.3 用户提示

| 场景 | 行为 |
|------|------|
| AI 禁用 | 无提示，正常流程 |
| API 密钥缺失 | 无提示，正常流程（配置中默认禁用） |
| 调用失败 | 提示："AI suggestion unavailable, using manual input" |
| 超时 | 提示："AI suggestion timed out, using manual input" |

---

## 五、测试策略

### 5.1 单元测试

| 模块 | 测试重点 |
|------|---------|
| `AIClient` | API 调用、错误处理、超时 |
| `AIService` | 业务逻辑、prompt 渲染、降级 |

### 5.2 Mock 策略

```python
# 测试 AIClient
from unittest.mock import Mock, patch

@patch("openai.OpenAI")
def test_ai_client(mock_openai):
    client = AIClient(config)
    result = client.generate_text("system", "user")
    assert result is not None

# 测试 AIService
def test_ai_service_with_mock_client():
    mock_client = Mock()
    mock_client.generate_text.return_value = "suggestion"
    service = AIService(ai_client=mock_client)
    result = service.suggest_flow_slug("issue title")
    assert result is not None
```

### 5.3 集成测试

```python
def test_flow_new_with_ai():
    result = runner.invoke(app, ["flow", "new", "--ai", "--issue", "220"])
    assert result.exit_code == 0
```

---

## 六、扩展性考虑

### 6.1 未来扩展场景

1. **支持更多 AI 后端**:
   - 当前：OpenAI 兼容 API（通过 `base_url`）
   - 未来：可直接添加 `AnthropicClient`、`GeminiClient`

2. **支持更多命令**:
   - 当前：`pr create`（`flow new --ai` 已移除）
   - 未来：`flow review`、`commit message` 等

3. **支持自定义 prompts**:
   - 当前：从 `config/prompts.yaml` 加载
   - 未来：支持用户指定 prompt 文件路径

### 6.2 扩展点设计

**Client 接口（可选，暂时不需要）**:
```python
# 如果未来需要支持多种后端，再引入 Protocol
class AIClientProtocol(Protocol):
    def generate_text(...) -> str | None: ...

# 当前不需要，直接使用 AIClient 即可
```

**Service 扩展**:
```python
class AIService:
    def register_prompt(self, name: str, template: str) -> None:
        """注册自定义 prompt 模板"""
        ...

    def generate_with_template(
        self,
        template_name: str,
        **variables
    ) -> str | None:
        """使用指定模板生成文本"""
        ...
```

---

## 七、成功标准

- [ ] `vibe3 pr create --ai` 能生成 title/body 建议
- [ ] `vibe3 pr create --ai` 能生成 PR 内容建议
- [ ] AI 禁用时行为正常
- [ ] AI 失败时优雅降级
- [ ] 测试覆盖率 >= 70%
- [ ] 支持 OpenAI 兼容 API（Ollama、vLLM 等）

---

## 八、文件清单

### 新增文件

| 文件 | 职责 | 行数估计 |
|------|------|---------|
| `src/vibe3/clients/ai_client.py` | AI API 客户端 | ~80 |
| `src/vibe3/services/ai_service.py` | AI 服务 | ~100 |
| `config/prompts.yaml` | Prompts 配置 | ~60 |
| `tests/vibe3/clients/test_ai_client.py` | 客户端测试 | ~120 |
| `tests/vibe3/services/test_ai_service.py` | 服务测试 | ~100 |

### 修改文件

| 文件 | 改动量 |
|------|-------|
| `pyproject.toml` | +1 行 |
| `config/settings.yaml` | +8 行 |
| `src/vibe3/config/settings.py` | +15 行 |
| `src/vibe3/commands/flow.py` | +20 行 |
| `src/vibe3/commands/pr_create.py` | +20 行 |

**总代码量**: ~500 行（含测试）

---

## 九、实施顺序

```
Phase 1 (基础设施)
  ↓
Phase 2 (Client 层 + 测试)
  ↓
Phase 3 (Service 层 + 测试)
  ↓
Phase 4 (Command 集成 + 测试)
```

**预计工作量**: 1-2 天
