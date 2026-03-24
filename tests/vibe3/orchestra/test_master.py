"""Tests for Orchestra master agent."""

from vibe3.orchestra.master import TriageDecision, parse_triage_response


def test_parse_valid_response():
    output = '{"action": "triage", "reason": "valid feature request"}'
    decision = parse_triage_response(output)
    assert decision.action == "triage"
    assert decision.reason == "valid feature request"


def test_parse_close_response():
    output = '{"action": "close", "reason": "duplicate", '
    output += '"comment_body": "Closing as duplicate"}'
    decision = parse_triage_response(output)
    assert decision.action == "close"
    assert decision.comment_body == "Closing as duplicate"


def test_parse_comment_response():
    output = '{"action": "comment", "reason": "need more info", '
    output += '"comment_body": "Please provide details"}'
    decision = parse_triage_response(output)
    assert decision.action == "comment"
    assert decision.comment_body == "Please provide details"


def test_parse_invalid_json():
    output = "not json"
    decision = parse_triage_response(output)
    assert decision.action == "none"
    assert "Failed to parse" in decision.reason


def test_decision_is_valid():
    assert TriageDecision(action="close", reason="test").is_valid()
    assert TriageDecision(action="triage", reason="test").is_valid()
    assert TriageDecision(action="comment", reason="test").is_valid()
    assert TriageDecision(action="none", reason="test").is_valid()
    assert not TriageDecision(action="invalid", reason="test").is_valid()
