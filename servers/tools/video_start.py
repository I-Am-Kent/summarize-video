"""
Tool: video_start
Purpose: Start a video download and transcription job, returning a job_id immediately.
Timeout strategy: start/check polling pattern — Claude Desktop 60s limit.
"""

import os

import requests

_BASE_URL = f"http://127.0.0.1:{os.environ.get('SERVER_PORT', '9731')}"

VALID_MODES = ("summary", "transcript", "key_points", "action_items")


def video_start(url: str, mode: str = "summary") -> str:
    """
    Start a video transcription job for any URL supported by yt-dlp.

    WHEN to use: Use this tool when the user provides a video URL and wants it
    transcribed, summarized, or analyzed. Supports YouTube, Instagram, TikTok,
    Vimeo, Twitter/X, and 1000+ other platforms via yt-dlp.

    HOW to call:
    - url: The full video URL (e.g., "https://www.youtube.com/watch?v=...")
    - mode: One of four output modes:
        * "summary" (default) — returns transcript + summarization instruction
        * "transcript" — returns raw verbatim transcript only
        * "key_points" — returns transcript + key points extraction instruction
        * "action_items" — returns transcript + actionable takeaways instruction

    WHAT returns: A job_id string that you MUST pass to video_check to get results.
    The job runs asynchronously — this tool returns immediately. Do NOT assume
    results are ready; always call video_check with the returned job_id.

    Example:
        video_start(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", mode="summary")
        → "Job started. ID: abc123-... Call video_check(job_id='abc123-...') in 15-20 seconds."

    Do NOT use this tool for local files or non-video URLs.
    Do NOT fabricate job IDs — always use exactly what this tool returns.
    """
    try:
        from launcher import ensure_server  # noqa: PLC0415
        err = ensure_server()
        if err:
            return err

        if mode not in VALID_MODES:
            return (
                f"ERROR: Invalid mode '{mode}'. "
                f"Choose one of: {', '.join(VALID_MODES)}"
            )

        if not url or not url.startswith(("http://", "https://")):
            return "ERROR: url must be a full HTTP/HTTPS URL."

        resp = requests.post(
            f"{_BASE_URL}/start",
            json={"url": url, "mode": mode},
            timeout=290,
        )
        data = resp.json()
        if "job_id" in data:
            job_id = data["job_id"]
            return (
                f"Job started. ID: {job_id}\n\n"
                f"Call video_check(job_id='{job_id}') in 15-20 seconds to get results."
            )
        return f"ERROR: {data.get('error', 'Unexpected response from server.')}"

    except requests.ConnectionError:
        return "ERROR: Lost connection to processing server. Try again."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
