"""Tests for Serena client helper functions."""

from vibe3.clients.serena_client import extract_function_locations


class TestExtractFunctionLocations:
    """extract_function_locations tests."""

    def test_simple_string_list_returns_empty_dict(self) -> None:
        """Test with simple string list (no location) -> empty dict."""
        payload = {"Function": ["foo"]}
        result = extract_function_locations(payload)
        assert result == {}

    def test_function_with_body_location(self) -> None:
        """Test with function node containing body_location."""
        payload = {
            "kind": 12,
            "name_path": "foo",
            "body_location": {"start_line": 10, "end_line": 25},
        }
        result = extract_function_locations(payload)
        assert result == {"foo": {"start_line": 10, "end_line": 25}}

    def test_nested_functions_in_class(self) -> None:
        """Test with nested functions (class containing methods)."""
        payload = {
            "kind": 5,
            "name": "MyClass",
            "Function": [
                {
                    "name_path": "MyClass.method1",
                    "body_location": {"start_line": 5, "end_line": 10},
                },
                {
                    "name_path": "MyClass.method2",
                    "body_location": {"start_line": 15, "end_line": 20},
                },
            ],
        }
        result = extract_function_locations(payload)
        assert result == {
            "MyClass.method1": {"start_line": 5, "end_line": 10},
            "MyClass.method2": {"start_line": 15, "end_line": 20},
        }

    def test_missing_body_location_defaults_to_zero(self) -> None:
        """Test that missing body_location defaults to 0,0."""
        payload = {
            "kind": 12,
            "name_path": "foo",
        }
        result = extract_function_locations(payload)
        assert result == {"foo": {"start_line": 0, "end_line": 0}}

    def test_partial_body_location_defaults_to_zero(self) -> None:
        """Test that partial body_location defaults missing fields to 0."""
        payload = {
            "kind": 12,
            "name_path": "foo",
            "body_location": {"start_line": 10},  # Missing end_line
        }
        result = extract_function_locations(payload)
        assert result == {"foo": {"start_line": 10, "end_line": 0}}

    def test_multiple_functions(self) -> None:
        """Test extracting locations from multiple functions."""
        payload = {
            "Function": [
                {
                    "name_path": "func1",
                    "body_location": {"start_line": 1, "end_line": 10},
                },
                {
                    "name_path": "func2",
                    "body_location": {"start_line": 15, "end_line": 25},
                },
            ]
        }
        result = extract_function_locations(payload)
        assert result == {
            "func1": {"start_line": 1, "end_line": 10},
            "func2": {"start_line": 15, "end_line": 25},
        }

    def test_duplicate_function_names_keeps_first(self) -> None:
        """Test that duplicate function names keep first occurrence."""
        payload = {
            "Function": [
                {
                    "name_path": "foo",
                    "body_location": {"start_line": 1, "end_line": 10},
                },
                {
                    "name_path": "foo",
                    "body_location": {"start_line": 20, "end_line": 30},
                },
            ]
        }
        result = extract_function_locations(payload)
        assert result == {"foo": {"start_line": 1, "end_line": 10}}

    def test_function_node_uses_name_when_name_path_missing(self) -> None:
        """Test that function node uses 'name' when 'name_path' is missing."""
        payload = {
            "kind": 12,
            "name": "bar",
            "body_location": {"start_line": 5, "end_line": 15},
        }
        result = extract_function_locations(payload)
        assert result == {"bar": {"start_line": 5, "end_line": 15}}

    def test_nested_function_dict_uses_name_when_name_path_missing(self) -> None:
        """Test nested function dict uses 'name' when 'name_path' is missing."""
        payload = {
            "Function": [
                {
                    "name": "baz",
                    "body_location": {"start_line": 3, "end_line": 8},
                }
            ]
        }
        result = extract_function_locations(payload)
        assert result == {"baz": {"start_line": 3, "end_line": 8}}
