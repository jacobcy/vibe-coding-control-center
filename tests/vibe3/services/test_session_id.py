from vibe3.agents.backends.codeagent import extract_session_id


def test_extract_session_id_valid():
    stdout = (
        "Some output\nSESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8\nMore output"
    )
    assert extract_session_id(stdout) == "262f0fea-eacb-4223-b842-b5b5097f94e8"


def test_extract_session_id_none():
    assert extract_session_id(None) is None
    assert extract_session_id("") is None


def test_extract_session_id_no_match():
    stdout = "Some output without session id"
    assert extract_session_id(stdout) is None


def test_extract_session_id_different_spacing():
    stdout = "SESSION_ID:262f0fea-eacb-4223-b842-b5b5097f94e8"
    assert extract_session_id(stdout) == "262f0fea-eacb-4223-b842-b5b5097f94e8"

    stdout = "SESSION_ID:    262f0fea-eacb-4223-b842-b5b5097f94e8"
    assert extract_session_id(stdout) == "262f0fea-eacb-4223-b842-b5b5097f94e8"
