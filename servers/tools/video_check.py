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

    WHEN to use: Call this 5 seconds after video_start, then follow the interval
    each response tells you. Do NOT stop after one check if status is "running".

    HOW to call:
    - job_id: The exact job_id string returned by video_start. Do NOT modify or
      truncate the ID. Do NOT fabricate IDs.

    WHAT returns:
    - "running (downloading)" — fetching video, check again in 5 seconds
    - "running (transcribing, ~Xs remaining)" — transcribing, check at given interval
    - "complete" — job finished, transcript and instructions included in response
    - "failed" — job encountered an error, details included in response
    - "not found" — no job with this ID (lost on server restart, start a new job)

    Example:
        video_check(job_id="abc123-def456-...")
        → "Status: running (downloading). Call this tool again in 5 seconds."
        → "Status: running (transcribing, ~42s remaining). Call this tool again in 30 seconds."
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
            stage = data.get("stage", "unknown")
            eta = data.get("eta_seconds")
            if stage == "transcribing" and eta is not None:
                if eta > 15:
                    interval = min(eta, 30)
                    return (
                        f"Status: running (transcribing, ~{eta}s remaining). "
                        f"Call this tool again in {interval} seconds."
                    )
                else:
                    return (
                        f"Status: running (transcribing, ~{eta}s remaining). "
                        f"Call this tool again in 5 seconds."
                    )
            return f"Status: running ({stage}). Call this tool again in 5 seconds."

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
