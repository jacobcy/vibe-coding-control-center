"""Tests for server utility functions."""

from unittest.mock import patch

import pytest
import typer

from vibe3.server import find_available_port


def test_find_available_port_returns_start_when_available() -> None:
    """Test that find_available_port returns start port when available."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value
        mock_sock.bind.return_value = None  # Port is available

        port, was_auto_discovered = find_available_port(8080)
        assert port == 8080
        assert was_auto_discovered is False


def test_find_available_port_falls_back_when_occupied_with_max_port() -> None:
    """Test that find_available_port falls back to next port when start is
    occupied and max_port is explicitly set (auto-discovery enabled)."""
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

        port, was_auto_discovered = find_available_port(8080, max_port=8090)
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


def test_find_available_port_caps_at_65535() -> None:
    """Test that find_available_port caps effective_max_port at 65535
    to avoid OverflowError."""
    with patch("socket.socket") as mock_socket:
        mock_sock = mock_socket.return_value.__enter__.return_value
        # All ports are occupied
        mock_sock.bind.side_effect = OSError(48, "Address already in use")

        with pytest.raises(typer.Exit):
            # Request port 65530-65540, which should cap at 65535
            find_available_port(65530, max_port=65540)

        # Should have tried 6 ports (65530-65535 inclusive), not 11
        assert mock_sock.bind.call_count == 6


def test_find_available_port_validates_inverted_range() -> None:
    """Test that find_available_port raises typer.Exit(1) when max_port < start_port."""
    with pytest.raises(typer.Exit) as exc_info:
        find_available_port(8080, max_port=8070)

    assert exc_info.value.exit_code == 1
