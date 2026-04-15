"""Tests for the video_check tool."""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "servers"))


def _import_tool():
    from tools.video_check import video_check
    return video_check


def test_video_check_empty_job_id():
    """Rejects empty job_id immediately."""
    video_check = _import_tool()
    import launcher
    with patch.object(launcher, "ensure_server", return_value=None):
        result = video_check(job_id="")
    assert "ERROR" in result


def test_video_check_running_status():
    """Returns polling instruction when job is running (downloading stage)."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running", "stage": "downloading"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "running" in result.lower()
    assert "downloading" in result
    assert "5 seconds" in result


def test_video_check_transcribing_high_eta():
    """Suggests longer poll interval when ETA is high."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "running", "stage": "transcribing", "eta_seconds": 45,
        "audio_duration": 600.0, "transcribe_started": 1000000.0,
    }

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "transcribing" in result
    assert "45s remaining" in result
    assert "30 seconds" in result  # capped at min(45, 30)


def test_video_check_transcribing_low_eta():
    """Suggests 5-second poll when ETA is low."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "running", "stage": "transcribing", "eta_seconds": 8,
        "audio_duration": 120.0, "transcribe_started": 1000000.0,
    }

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "transcribing" in result
    assert "8s remaining" in result
    assert "5 seconds" in result


def test_video_check_extracting_stage():
    """Shows extracting stage with fast poll."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running", "stage": "extracting"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "extracting" in result
    assert "5 seconds" in result


def test_video_check_loading_model_stage():
    """Shows model loading stage with fast poll."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running", "stage": "loading_model"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "loading_model" in result
    assert "5 seconds" in result


def test_video_check_no_stage_backward_compat():
    """Handles response without stage field gracefully."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "running" in result.lower()
    assert "5 seconds" in result


def test_video_check_complete_status():
    """Returns transcript result when job is complete."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "complete", "result": "[TRANSCRIPT]\nHello world"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "complete" in result.lower()
    assert "Hello world" in result


def test_video_check_failed_status():
    """Returns error detail when job failed."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "failed", "error": "Download timed out"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="some-job-id")

    assert "failed" in result.lower()
    assert "Download timed out" in result


def test_video_check_not_found():
    """Returns clear message when job_id is unknown."""
    video_check = _import_tool()
    import launcher
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "not_found"}

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", return_value=mock_resp):
        result = video_check(job_id="unknown-id")

    assert "not found" in result.lower()
    assert "video_start" in result  # tells user to start a new job


def test_video_check_server_error_propagates():
    """Returns ensure_server error without calling HTTP endpoint."""
    video_check = _import_tool()
    import launcher
    with patch.object(launcher, "ensure_server", return_value="ERROR: server crashed"):
        result = video_check(job_id="some-job-id")
    assert "ERROR" in result
    assert "server crashed" in result


def test_video_check_connection_error():
    """Returns error string on connection failure — does not raise."""
    video_check = _import_tool()
    import launcher
    import requests as req

    with patch.object(launcher, "ensure_server", return_value=None), \
         patch("tools.video_check.requests.get", side_effect=req.ConnectionError("refused")):
        result = video_check(job_id="some-job-id")

    assert "ERROR" in result
    assert isinstance(result, str)
