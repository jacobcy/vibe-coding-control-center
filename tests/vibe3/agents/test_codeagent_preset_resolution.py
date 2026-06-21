"""Tests for backend to agent preset resolution."""

from vibe3.agents.backends.codeagent import _resolve_backend_to_agent_preset


class TestResolveBackendToAgentPreset:
    """Test the _resolve_backend_to_agent_preset helper function."""

    def test_resolve_claude_backend_returns_preset(self, monkeypatch):
        """Should return 'vibe-planner' for claude backend."""
        mock_models = {
            "agents": {
                "vibe-planner": {
                    "backend": "claude",
                    "model": "claude-3-5-sonnet-20241022",
                },
                "vibe-governance": {"backend": "claude", "yolo": True},
            }
        }
        monkeypatch.setattr(
            "vibe3.config.read_models_json",
            lambda _: mock_models,
        )

        result = _resolve_backend_to_agent_preset("claude")
        assert result == "vibe-planner"  # First match

    def test_resolve_gemini_backend_returns_preset(self, monkeypatch):
        """Should return preset name for gemini backend."""
        mock_models = {
            "agents": {
                "vibe-gemini": {"backend": "gemini", "model": "gemini-2.0-flash-exp"},
            }
        }
        monkeypatch.setattr(
            "vibe3.config.read_models_json",
            lambda _: mock_models,
        )

        result = _resolve_backend_to_agent_preset("gemini")
        assert result == "vibe-gemini"

    def test_resolve_unknown_backend_returns_none(self, monkeypatch):
        """Should return None for unknown backends."""
        mock_models = {"agents": {}}
        monkeypatch.setattr(
            "vibe3.config.read_models_json",
            lambda _: mock_models,
        )

        result = _resolve_backend_to_agent_preset("unknown-backend")
        assert result is None

    def test_resolve_with_no_agents_dict_returns_none(self, monkeypatch):
        """Should return None when agents is not a dict."""
        mock_models = {"agents": None}
        monkeypatch.setattr(
            "vibe3.config.read_models_json",
            lambda _: mock_models,
        )

        result = _resolve_backend_to_agent_preset("claude")
        assert result is None

    def test_resolve_with_malformed_agent_config_returns_none(self, monkeypatch):
        """Should skip malformed agent configs."""
        mock_models = {
            "agents": {
                "valid-agent": {"backend": "claude"},
                "invalid-agent": "not-a-dict",
                "another-invalid": {"model": "claude"},  # Missing backend
            }
        }
        monkeypatch.setattr(
            "vibe3.config.read_models_json",
            lambda _: mock_models,
        )

        result = _resolve_backend_to_agent_preset("claude")
        assert result == "valid-agent"
