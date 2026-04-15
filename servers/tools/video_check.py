"""
Tool: video_check
Purpose: Poll the status of a video transcription job started by video_start.
"""

import os

import requests

_BASE_URL = f"http://127.0.0.1:{os.environ.get('SERVER_PORT', '9731')}"


def video_check(job_id: str) -> str:
    """
    Check the status of a video transcription job.

    WHEN to use: Call this every 15-20 seconds after calling video_start, until
    you receive a "complete" or "failed" status. Do NOT stop after one check if
    status is "running" — videos can take 1-5 minutes to download and transcribe.

    HOW to call:
    - job_id: The exact job_id string returned by video_start. Do NOT modify or
      truncate the ID. Do NOT fabricate IDs.

    WHAT returns:
    - "running" — job is still in progress, call again in 15-20 seconds
    - "complete" — job finished, transcript and instructions are included in response
    - "failed" — job encountered an error, details included in response
    - "not found" — no job with this ID exists (may have been lost on server restart)

    Example:
        video_check(job_id="abc123-def456-...")
        → "Status: running. Call this tool again in 15-20 seconds."
        → "Status: complete.\n\n[TRANSCRIPT]\n..."

    Do NOT assume the job is done without checking — always poll.
    Do NOT call this tool with a job_id from a previous session (jobs are in-memory).
    """
    try:
        from launcher import ensure_server  # noqa: PLC0415
        err = ensure_server()
        if err:
            return err

        if not job_id or not job_id.strip():
            return "ERROR: job_id must not be empty."

        resp = requests.get(
            f"{_BASE_URL}/check/{job_id.strip()}",
            timeout=30,
        )
        data = resp.json()
        status = data.get("status", "unknown")

        if status == "running":
            return "Status: running. Call this tool again in 15-20 seconds."

        if status == "complete":
            result = data.get("result", "")
            return f"Status: complete.\n\n{result}"

        if status == "failed":
            error = data.get("error", "Unknown error")
            return f"Status: failed. Error: {error}"

        if status == "not_found":
            return (
                f"Status: not found. No job with ID '{job_id}' exists. "
                "Jobs are in-memory and lost if the server restarted. "
                "Start a new job with video_start."
            )

        return f"ERROR: Unexpected status '{status}' from server."

    except requests.ConnectionError:
        return "ERROR: Lost connection to processing server. Try again."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
