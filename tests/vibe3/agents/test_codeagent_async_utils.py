"""Tests for CodeagentBackend - utility functions (session_id, log_filter)."""


class TestSessionIdExtraction:
    def test_extract_session_id_supports_modern_wrapper_format(self) -> None:
        from vibe3.agents.backends.session_manager import extract_session_id

        output = "some text\nSESSION_ID: ses_2aea4d6b6ffexDUssWC9tEP4Nh\nmore text\n"

        assert extract_session_id(output) == "ses_2aea4d6b6ffexDUssWC9tEP4Nh"

    def test_extract_session_id_supports_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.session_manager import extract_session_id

        output = '{"type":"step_start","sessionID":"ses_2ae4422c7ffeYDHGar7ZxRsnTC"}'

        assert extract_session_id(output) == "ses_2ae4422c7ffeYDHGar7ZxRsnTC"

    def test_extract_session_id_supports_escaped_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.session_manager import extract_session_id

        output = (
            '{"message":"{\\"type\\":\\"step_start\\",'
            '\\"sessionID\\":\\"ses_2ae0c24f2ffehx2ejWE21YTtHi\\"}"}'
        )

        assert extract_session_id(output) == "ses_2ae0c24f2ffehx2ejWE21YTtHi"
