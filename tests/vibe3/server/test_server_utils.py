"""Tests for server utility functions."""

from unittest.mock import patch

import pytest
import typer

from vibe3.server.server_utils import find_available_port


def test_find_available_port_returns_start_when_available() -> None:
    """Test that find_available_port returns start port when available."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value
        mock_sock.bind.return_value = None  # Port is available

        port, was_auto_discovered = find_available_port(8080)
        assert port == 8080
        assert was_auto_discovered is False


def test_find_available_port_falls_back_when_occupied() -> None:
    """Test that find_available_port falls back to next port when start is occupied."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value

        # First port (8080) is occupied, second (8081) is available
        call_count = [0]

        def mock_bind(addr):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError(48, "Address already in use")
            # Second call succeeds

        mock_sock.bind.side_effect = mock_bind

        port, was_auto_discovered = find_available_port(8080)
        assert port == 8081
        assert was_auto_discovered is True


def test_find_available_port_exits_when_all_occupied() -> None:
    """Test that find_available_port raises typer.Exit(1) when all ports
    in range are occupied."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value
        mock_sock.bind.side_effect = OSError(48, "Address already in use")

        with pytest.raises(typer.Exit) as exc_info:
            find_available_port(8080, max_port=8082)

        assert exc_info.value.exit_code == 1


def test_find_available_port_uses_default_range_when_max_port_is_none() -> None:
    """Test that find_available_port defaults to start_port + 10 when
    max_port is None."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value
        mock_sock.bind.side_effect = OSError(48, "Address already in use")

        with pytest.raises(typer.Exit):
            find_available_port(8080, max_port=None)

        # Should have tried 11 ports (8080-8090 inclusive)
        assert mock_sock.bind.call_count == 11
