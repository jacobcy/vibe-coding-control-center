"""Configuration models using pydantic for type safety.

配置真源原则：
- config/v3/settings.yaml 是运行时开关、agent preset、policy 路径等配置真源
- config/prompts/prompts.yaml 是 prompt 文案真源
- config/prompts/prompt-recipes.yaml 是 role prompt section 装配顺序真源
- Pydantic 模型只提供最小安全默认值（用于降级场景）
- 正常情况下所有配置都从 YAML 文件读取
"""

import warnings
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, model_validator

from vibe3.config.orchestra_config import OrchestraConfig
from vibe3.config.settings_check_cleanup import CheckCleanupSettings
from vibe3.config.settings_pr import (
    FileChangeWeights,
    LineChangeWeights,
    MergeGateConfig,
    ModuleChangeWeights,
    PRScoringConfig,
    PRScoringThresholds,
    PRScoringWeights,
    SizeThreshold,
    SizeThresholds,
)


def _vibe3_config_root() -> Path:
    """Find the vibe3 config root directory by walking up from this module.

    Returns the directory containing config/v3/settings.yaml, which is the vibe3
    installation root (repo root for source installs, ~/.vibe for pip installs).

    Used as fallback when CWD-relative config paths fail (cross-project invocation).
    """
    # Start from this module's location
    current = Path(__file__).resolve()

    # Walk up to find the directory containing config/v3/settings.yaml
    # Max 10 levels to prevent infinite loops
    for _ in range(10):
        parent = current.parent
        if parent == current:
            # Reached filesystem root, stop
            break

        # Check if this parent contains config/v3/settings.yaml
        if (parent / "config" / "v3" / "settings.yaml").exists():
            return parent

        current = parent

    # Fallback: return parent of src/ directory (repo root for source installs)
    # This handles the case where config/v3/settings.yaml doesn't exist yet
    # Walk up from __file__ to find the directory containing src/vibe3/
    current = Path(__file__).resolve()
    for _ in range(10):
        parent = current.parent
        if parent == current:
            break
        if (parent / "src" / "vibe3").exists():
            return parent
        current = parent

    # Last resort: return current working directory
    return Path.cwd()


class AIConfig(BaseModel):
    """AI 辅助配置.

    用于 AI 辅助文案能力（如 pr create --ai）。
    """

    api_key_env: str = Field(default="DEEPSEEK_API_KEY")
    base_url: str = Field(default="https://api.deepseek.com/v1")
    model: str = Field(default="deepseek/deepseek-chat")
    timeout: int = Field(default=30, ge=1, le=300)


class AgentPromptConfig(BaseModel):
    """Global prompt instructions applied to all code agents."""

    global_notice: str = Field(default="")


class FlowConfig(BaseModel):
    """Flow 管理配置."""

    protected_branches: list[str] = Field(
        default_factory=lambda: ["main", "master", "develop"],
        description="Branches that cannot have flows",
    )


# fmt: off
__all__ = ["AIConfig", "FlowConfig", "PRScoringConfig", "MergeGateConfig",
           "PRScoringWeights", "PRScoringThresholds", "LineChangeWeights",
           "FileChangeWeights", "ModuleChangeWeights", "SizeThreshold",
           "SizeThresholds", "VibeConfig", "DocLimitsConfig", "CodeLimitsConfig",
           "CheckCleanupSettings"]
# fmt: on

# Prompt content fields in prompts.yaml that map to VibeConfig sections.
# Template-only keys (like "default", "plan", "skill") are excluded.
_PROMPT_KEYS: dict[str, set[str]] = {
    "agent_prompt": {"global_notice"},
    "review": {"output_format", "review_task", "retry_task", "review_prompt"},
    "plan": {"output_format", "plan_task", "retry_task", "plan_prompt"},
    "run": {
        "output_format",
        "run_task",
        "publish_task",
        "coding_task",
        "retry_task",
        "run_prompt",
    },
}


def _merge_prompt_fields(data: dict, prompts: dict) -> None:
    """Merge prompt content from prompts.yaml into VibeConfig-compatible sections.

    Prompt text belongs in config/prompts/prompts.yaml. If config/v3/settings.yaml
    also defines these fields, it creates a dual source of truth, so fail fast.
    """
    for section, allowed in _PROMPT_KEYS.items():
        src = prompts.get(section)
        if not isinstance(src, dict):
            continue
        dst = data.setdefault(section, {})
        for key in allowed:
            if key in dst:
                raise ValueError(
                    f"Prompt field '{section}.{key}' must live in "
                    "config/prompts/prompts.yaml, not config/v3/settings.yaml"
                )
            if key in src:
                dst[key] = src[key]


class SingleFileLocConfig(BaseModel):
    """单文件行数限制."""

    warning_threshold: int = Field(
        default=300,
        validation_alias=AliasChoices("warning_threshold", "default"),
        description="本地开发建议值（WARNING 级别）",
    )
    ci_block_threshold: int = Field(
        default=400,
        validation_alias=AliasChoices("ci_block_threshold", "max"),
        description="CI 强制阻塞值（BLOCK 级别）",
    )
    exceptions: list["LocExceptionConfig"] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def warn_deprecated_fields(cls, data: dict) -> dict:
        """如果使用旧字段名，发出弃用警告."""
        if "default" in data:
            warnings.warn(
                "Field 'default' is deprecated, use 'warning_threshold' instead",
                FutureWarning,
                stacklevel=2,
            )
        if "max" in data:
            warnings.warn(
                "Field 'max' is deprecated, use 'ci_block_threshold' instead",
                FutureWarning,
                stacklevel=2,
            )
        return data

    @model_validator(mode="after")
    def validate_unique_exception_paths(self) -> "SingleFileLocConfig":
        seen_paths: set[str] = set()
        for entry in self.exceptions:
            if entry.path in seen_paths:
                raise ValueError(f"Duplicate LOC exception path: {entry.path}")
            seen_paths.add(entry.path)
        return self


class LocExceptionConfig(BaseModel):
    """单文件 LOC 例外配置."""

    path: str
    limit: int = Field(default=400, ge=1)
    reason: str = Field(default="")


class TotalFileLocConfig(BaseModel):
    """总行数限制."""

    v2_shell: int = Field(default=4000)
    v3_python: int = Field(default=32000)


class CodePathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class ScriptsPathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class TestPathsConfig(BaseModel):
    v2_shell: list[str] = Field(default_factory=list)
    v3_python: list[str] = Field(default_factory=list)


class CodeLimitsConfig(BaseModel):
    """代码量限制配置."""

    single_file_loc: SingleFileLocConfig = Field(default_factory=SingleFileLocConfig)
    total_file_loc: TotalFileLocConfig = Field(default_factory=TotalFileLocConfig)
    code_paths: CodePathsConfig = Field(default_factory=CodePathsConfig)
    scripts_paths: ScriptsPathsConfig = Field(default_factory=ScriptsPathsConfig)
    test_paths: TestPathsConfig = Field(default_factory=TestPathsConfig)


class DocLimitsConfig(BaseModel):
    """文档量限制配置."""

    single_file_loc: SingleFileLocConfig = Field(default_factory=SingleFileLocConfig)


class ReviewScopeConfig(BaseModel):
    """Review scope configuration."""

    critical_paths: list[str] = Field(default_factory=list)
    public_api_paths: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Agent configuration for codeagent-wrapper.

    When using a preset (agent specified), backend/model can still be provided
    for database recording purposes. If backend is None, agent is passed to
    codeagent-wrapper as preset name. If backend is provided, it overrides
    the preset's backend/model.

    Actor resolution:
    - If backend is provided: use backend/model directly
    - If only agent is provided: use agent as identifier (preset name)
    """

    agent: str | None = Field(default=None)
    backend: str | None = Field(default=None)
    model: str | None = Field(default=None)
    timeout_seconds: int = Field(default=3600, ge=1)


class PolicyResolverMixin:
    """Mixin providing a common base type for policy config classes.

    Used by ReviewConfig, PlanConfig, RunConfig to share type identity.
    Subclasses declare policy_file and common_rules as their own Pydantic fields.
    """

    __slots__ = ()


class ReviewConfig(BaseModel, PolicyResolverMixin):
    """Review configuration."""

    policy_file: str | None = Field(
        default=None,
        description="Path to review policy (None = use profile resolution)",
    )
    common_rules: str | None = Field(
        default=None, description="Path to common rules (None = use profile resolution)"
    )
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    review_task: str = Field(default="")
    retry_task: str = Field(default="")
    review_prompt: str = Field(default="")


class PlanConfig(BaseModel, PolicyResolverMixin):
    """Plan command configuration."""

    policy_file: str | None = Field(
        default=None, description="Path to plan policy (None = use profile resolution)"
    )
    common_rules: str | None = Field(
        default=None, description="Path to common rules (None = use profile resolution)"
    )
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    plan_task: str = Field(default="")
    retry_task: str = Field(default="")
    plan_prompt: str = Field(default="")


class RunConfig(BaseModel, PolicyResolverMixin):
    """Run command configuration."""

    policy_file: str | None = Field(
        default=None, description="Path to run policy (None = use profile resolution)"
    )
    common_rules: str | None = Field(
        default=None, description="Path to common rules (None = use profile resolution)"
    )
    agent_config: AgentConfig = Field(default_factory=AgentConfig)
    output_format: str = Field(default="")
    run_task: str = Field(default="")
    coding_task: str = Field(default="")
    retry_task: str = Field(default="")
    run_prompt: str = Field(default="")


class TestCoverageConfig(BaseModel):
    """Test coverage requirements."""

    services: int = Field(default=50, ge=0, le=100)
    clients: int = Field(default=50, ge=0, le=100)
    commands: int = Field(default=50, ge=0, le=100)


class QualityConfig(BaseModel):
    """Quality standards configuration."""

    test_coverage: TestCoverageConfig = Field(default_factory=TestCoverageConfig)


class VibeConfig(BaseModel):
    """Root configuration model."""

    agent_prompt: AgentPromptConfig = Field(default_factory=AgentPromptConfig)
    flow: FlowConfig = Field(default_factory=FlowConfig)
    doc_limits: DocLimitsConfig = Field(default_factory=DocLimitsConfig)
    code_limits: CodeLimitsConfig = Field(default_factory=CodeLimitsConfig)
    review_scope: ReviewScopeConfig = Field(default_factory=ReviewScopeConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    pr_scoring: PRScoringConfig = Field(default_factory=PRScoringConfig)
    plan: PlanConfig = Field(default_factory=PlanConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    orchestra: OrchestraConfig = Field(default_factory=OrchestraConfig)
    check_cleanup: CheckCleanupSettings = Field(default_factory=CheckCleanupSettings)

    @classmethod
    def _load_supplementary(cls, data: dict, config_path: Path | None = None) -> dict:
        """Merge LOC limits and prompt content from their migrated config files."""
        import yaml
        from loguru import logger

        # Determine base directory for resolving supplementary files
        if config_path is not None:
            # Use the directory containing the config file
            config_root = config_path.resolve().parent.parent  # config/v3/ -> config/
        else:
            config_root = None

        # Load loc_limits.yaml for code_limits and doc_limits
        # Try new path first, then fallback to old path
        new_loc_limits_path = Path("config/v3/loc_limits.yaml")
        if not new_loc_limits_path.exists():
            new_loc_limits_path = (
                _vibe3_config_root() / "config" / "v3" / "loc_limits.yaml"
            )
        old_loc_limits_path = Path("config/loc_limits.yaml")
        loc_limits_path = None

        if new_loc_limits_path.exists():
            loc_limits_path = new_loc_limits_path
        elif old_loc_limits_path.exists():
            logger.bind(domain="config", path=str(old_loc_limits_path)).warning(
                "Using deprecated loc_limits path config/loc_limits.yaml. "
                "Please migrate to config/v3/loc_limits.yaml"
            )
            loc_limits_path = old_loc_limits_path
        elif config_root is not None:
            # Try relative to config file
            root_loc_limits = config_root / "v3" / "loc_limits.yaml"
            if root_loc_limits.exists():
                loc_limits_path = root_loc_limits

        if loc_limits_path:
            with open(loc_limits_path) as f:
                supp = yaml.safe_load(f) or {}
            for key in ("doc_limits", "code_limits"):
                if key in supp and key not in data:
                    data[key] = supp[key]

        # Load prompt content from prompts.yaml into VibeConfig fields
        # Priority: paths.prompts_root (from installed settings.yaml) > repo-local paths
        prompts_path = None
        prompts_root_str = (data.get("paths") or {}).get("prompts_root")
        if prompts_root_str:
            installed_prompts_path = (
                Path(prompts_root_str).expanduser() / "prompts.yaml"
            )
            if installed_prompts_path.exists():
                prompts_path = installed_prompts_path

        if prompts_path is None:
            new_prompts_path = Path("config/prompts/prompts.yaml")
            old_prompts_path = Path("config/prompts.yaml")
            if new_prompts_path.exists():
                prompts_path = new_prompts_path
            elif old_prompts_path.exists():
                prompts_path = old_prompts_path
            elif config_root is not None:
                # Try relative to config file
                root_prompts = config_root / "prompts" / "prompts.yaml"
                if root_prompts.exists():
                    prompts_path = root_prompts

        if prompts_path:
            with open(prompts_path) as f:
                prompts = yaml.safe_load(f) or {}
            _merge_prompt_fields(data, prompts)

        return data

    @classmethod
    def _expand_config_variables(cls, config: dict) -> dict:
        """Expand variable references like ${paths.policies_root} in config values.

        Performs iterative expansion to handle nested references with cycle detection.
        Also expands ~ to home directory in path values.
        """
        import re
        from pathlib import Path
        from typing import Any, cast

        def expand_value(value: Any, context: dict[str, Any]) -> Any:
            if isinstance(value, str):
                # Expand ${...} variable references iteratively
                expanded = value
                max_iterations = 10  # Prevent infinite loops
                for _ in range(max_iterations):
                    pattern = r"\$\{([^}]+)\}"

                    def replace_var(match: re.Match[str]) -> str:
                        var_path = match.group(1)
                        # Navigate to referenced value
                        current: Any = context
                        for part in var_path.split("."):
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                # Variable not found, keep original reference
                                return match.group(0)
                        return (
                            str(current)
                            if not isinstance(current, dict)
                            else match.group(0)
                        )

                    new_expanded = re.sub(pattern, replace_var, expanded)
                    if new_expanded == expanded:
                        break  # No more changes, reached fixpoint
                    expanded = new_expanded

                # Expand ~ to home directory for path values
                if expanded.startswith("~") or "/~" in expanded:
                    expanded = str(Path(expanded).expanduser())

                return expanded
            elif isinstance(value, dict):
                return {k: expand_value(v, context) for k, v in value.items()}
            else:
                return value

        return cast(dict, expand_value(config, config))

    @classmethod
    def from_yaml(cls, config_path: Path) -> "VibeConfig":
        """Load configuration from YAML file."""
        import yaml

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        data = cls._load_supplementary(data, config_path)

        # Expand variable references before instantiation
        data = cls._expand_config_variables(data)

        return cls(**data)

    @classmethod
    def get_defaults(cls) -> "VibeConfig":
        """从迁移后的默认配置路径读取配置。"""
        new_default_path = Path("config/v3/settings.yaml")
        if new_default_path.exists():
            return cls.from_yaml(new_default_path)
        # Fallback: vibe3 installation default config
        root = _vibe3_config_root()
        root_new_path = root / "config" / "v3" / "settings.yaml"
        if root_new_path.exists():
            return cls.from_yaml(root_new_path)
        legacy_default_path = Path("config/settings.yaml")
        if legacy_default_path.exists():
            return cls.from_yaml(legacy_default_path)
        root_legacy_path = root / "config" / "settings.yaml"
        if root_legacy_path.exists():
            return cls.from_yaml(root_legacy_path)
        return cls()
