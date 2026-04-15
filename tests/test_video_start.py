"""Tests for the video_start tool."""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "servers"))


def _import_tool():
    from tools.video_start import video_start, VALID_MODES
    return video_start, VALID_MODES


def test_video_start_invalid_url():
    """Rejects non-HTTP URLs immediately."""
    video_start, _ = _import_tool()
    with patch("tools.video_start.requests.post"), \
         patch("tools.video_start.__import__"):
        # Patch ensure_server at launcher module level
        import launcher
        with patch.object(launcher, "ensure_server", return_value=None):
            result = video_start(url="not-a-url", mode="summary")
    assert "ERROR" in result
    assert "HTTP" in result or "url" in result.lower()


def test_video_start_invalid_mode():
    """Rejects unknown mode values."""
    video_start, _ = _import_tool()
    import launcher
    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_start.requests.post") as mock_post:
        result = video_start(url="https://www.youtube.com/watch?v=test", mode="invalid_mode")
    assert "ERROR" in result
    assert "mode" in result.lower() or "invalid" in result.lower()


def test_video_start_server_error_propagates():
    """Returns the error string from ensure_server when server fails."""
    video_start, _ = _import_tool()
    import launcher
    with patch.object(launcher, "ensure_server", return_value="ERROR: server not available"):
        result = video_start(url="https://www.youtube.com/watch?v=test", mode="summary")
    assert "ERROR" in result
    assert "server not available" in result


def test_video_start_returns_job_id_on_success():
    """Returns job_id and polling instructions on successful start."""
    video_start, _ = _import_tool()
    import launcher
    mock_response = MagicMock()
    mock_response.json.return_value = {"job_id": "test-uuid-1234"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_start.requests.post", return_value=mock_response):
        result = video_start(url="https://www.youtube.com/watch?v=test", mode="summary")

    assert "test-uuid-1234" in result
    assert "video_check" in result


def test_video_start_valid_modes():
    """All four valid modes are accepted."""
    video_start, VALID_MODES = _import_tool()
    import launcher
    mock_response = MagicMock()
    mock_response.json.return_value = {"job_id": "abc"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_start.requests.post", return_value=mock_response):
        for mode in VALID_MODES:
            result = video_start(url="https://www.youtube.com/watch?v=test", mode=mode)
            assert "abc" in result, f"Mode '{mode}' should succeed"


def test_video_start_connection_error():
    """Returns error string on connection failure — does not raise."""
    video_start, _ = _import_tool()
    import launcher
    import requests as req

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_start.requests.post", side_effect=req.ConnectionError("refused")):
        result = video_start(url="https://www.youtube.com/watch?v=test", mode="summary")

    assert "ERROR" in result
    assert isinstance(result, str)
