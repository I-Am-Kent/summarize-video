"""
video_http_server.py — Heavy Flask server for video download and transcription.

Spawned on-demand by launcher.py on first tool call. Self-terminates after
IDLE_TIMEOUT seconds of inactivity to free RAM (~850MB when model is warm).
The launcher detects the dead process and respawns on the next tool call.

Heavy imports (faster_whisper, yt_dlp, imageio_ffmpeg) are ALL lazy — imported
inside functions, never at module level. This keeps startup fast so the /health
endpoint responds before any model is loaded.

Flask is run with threaded=True so health checks during model load are not blocked.
"""

import argparse
import logging
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="summarize-video HTTP server")
parser.add_argument("--port", type=int, default=9731)
parser.add_argument("--idle-timeout", type=int, default=600)
parser.add_argument("--model-size", type=str, default="base.en")
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_dir = Path.home() / ".cache" / "summarize-video"
_log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(_log_dir / "http_server.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("http_server")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
app = Flask(__name__)
_jobs: dict[str, dict] = {}
_model = None
_model_lock = threading.Lock()
_last_call = time.time()
_executor = ThreadPoolExecutor(max_workers=2)

# ---------------------------------------------------------------------------
# Mode prompt instructions
# ---------------------------------------------------------------------------
MODE_INSTRUCTIONS = {
    "transcript": None,  # no instruction — raw transcript only
    "summary": (
        "Summarize this video transcript concisely, capturing the main topic, "
        "key arguments, and conclusion."
    ),
    "key_points": (
        "Extract the key points from this transcript as a bulleted list. "
        "Focus on the most important ideas, findings, or arguments."
    ),
    "action_items": (
        "Extract actionable steps and practical takeaways from this transcript. "
        "Format as a numbered list of specific things the viewer can do."
    ),
}


# ---------------------------------------------------------------------------
# ffmpeg — prefer system, fall back to imageio-ffmpeg bundled binary
# ---------------------------------------------------------------------------
def get_ffmpeg() -> str:
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg  # lazy
    return imageio_ffmpeg.get_ffmpeg_exe()


# ---------------------------------------------------------------------------
# Whisper model — lazy singleton
# ---------------------------------------------------------------------------
def get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel  # lazy
        model_dir = _log_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        log.info("Loading whisper model: %s", args.model_size)
        _model = WhisperModel(
            args.model_size,
            compute_type="int8",
            download_root=str(model_dir),
        )
        log.info("Whisper model loaded")
        return _model


# ---------------------------------------------------------------------------
# Idle watchdog — shut down after inactivity
# ---------------------------------------------------------------------------
def _watchdog():
    while True:
        time.sleep(60)
        idle = time.time() - _last_call
        if idle > args.idle_timeout:
            log.info("Idle timeout reached (%.0fs), shutting down", idle)
            if sys.platform == "win32":
                os._exit(0)
            else:
                os.kill(os.getpid(), signal.SIGTERM)


threading.Thread(target=_watchdog, daemon=True).start()


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok", "model_loaded": _model is not None})


@app.post("/start")
def start_job():
    global _last_call
    _last_call = time.time()

    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    mode = body.get("mode", "summary").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url must be a full HTTP/HTTPS URL"}), 400
    if mode not in MODE_INSTRUCTIONS:
        return jsonify({"error": f"mode must be one of: {', '.join(MODE_INSTRUCTIONS)}"}), 400

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "running", "stage": "downloading",
        "result": None, "error": None,
        "audio_duration": None, "transcribe_started": None, "eta_seconds": None,
    }
    _executor.submit(_process_video, job_id, url, mode)
    log.info("Job %s started: url=%s mode=%s", job_id, url, mode)

    return jsonify({"job_id": job_id})


@app.get("/check/<job_id>")
def check_job(job_id: str):
    global _last_call
    _last_call = time.time()

    job = _jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"})

    result = dict(job)  # shallow copy — don't mutate stored job
    if result.get("stage") == "transcribing" and result.get("transcribe_started"):
        elapsed = time.time() - result["transcribe_started"]
        remaining = max(0, int(result["audio_duration"] * 0.12 - elapsed))
        result["eta_seconds"] = remaining
    return jsonify(result)


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

def _process_video(job_id: str, url: str, mode: str) -> None:
    # TemporaryDirectory registers cleanup via atexit + __del__, giving better
    # coverage than mkdtemp+finally on normal shutdown. SIGKILL/OOM kills still
    # orphan the dir — the OS temp dir is cleaned on reboot in that case.
    with tempfile.TemporaryDirectory(prefix="summarize-video-") as tmp_dir:
        try:
            tmp_base = str(Path(tmp_dir) / "video")

            # --- Download ---
            log.info("Job %s: downloading %s", job_id, url)
            _download_video(url, tmp_base)

            # Find downloaded file (yt-dlp may append codec extension)
            video_file = _find_output_file(tmp_base)
            if not video_file:
                raise RuntimeError("Download produced no output file")

            # --- Extract audio ---
            _jobs[job_id]["stage"] = "extracting"
            log.info("Job %s: extracting audio", job_id)
            wav_path = str(Path(tmp_dir) / "audio.wav")
            _extract_audio(str(video_file), wav_path)

            # --- Transcribe ---
            _jobs[job_id]["stage"] = "loading_model" if _model is None else "transcribing"
            log.info("Job %s: transcribing", job_id)
            transcript = _transcribe(wav_path, job_id)

            # --- Format output ---
            output = _format_output(transcript, mode)

            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["stage"] = "complete"
            _jobs[job_id]["result"] = output
            log.info("Job %s: complete (%d chars)", job_id, len(output))

        except Exception as e:
            log.exception("Job %s failed: %s", job_id, e)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["stage"] = "failed"
            _jobs[job_id]["error"] = str(e)


def _download_video(url: str, output_template: str) -> None:
    import yt_dlp  # lazy

    ffmpeg_bin = get_ffmpeg()
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template + ".%(ext)s",
        "ffmpeg_location": ffmpeg_bin,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def _find_output_file(base: str) -> Path | None:
    """yt-dlp appends the codec extension — check several possibilities."""
    parent = Path(base).parent
    stem = Path(base).name
    for p in parent.iterdir():
        if p.stem == stem:
            return p
    # Also try without stem match (yt-dlp can rename files)
    files = sorted(parent.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _extract_audio(video_path: str, wav_path: str) -> None:
    import subprocess as sp  # lazy inside function for clarity

    ffmpeg = get_ffmpeg()
    with open(str(_log_dir / "ffmpeg.log"), "a", encoding="utf-8", errors="replace") as log_f:
        proc = sp.Popen(
            [
                ffmpeg, "-y", "-i", video_path,
                "-ac", "1", "-ar", "16000",
                "-vn", wav_path,
            ],
            stdout=log_f,
            stderr=log_f,
        )
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode}")


def _transcribe(wav_path: str, job_id: str) -> str:
    model = get_model()
    _jobs[job_id]["stage"] = "transcribing"  # update after model load in case it was cold
    segments, info = model.transcribe(wav_path, beam_size=5)
    # info.duration is available immediately — segments are a lazy generator
    _jobs[job_id]["audio_duration"] = info.duration
    _jobs[job_id]["transcribe_started"] = time.time()
    _jobs[job_id]["eta_seconds"] = int(info.duration * 0.12)
    parts = []
    for seg in segments:
        text = seg.text.strip()
        if text and text not in ("[BLANK_AUDIO]", "[MUSIC]"):
            parts.append(text)
    return " ".join(parts)


def _format_output(transcript: str, mode: str) -> str:
    instruction = MODE_INSTRUCTIONS.get(mode)
    if not instruction:
        return f"[TRANSCRIPT]\n{transcript}"
    return f"[TRANSCRIPT]\n{transcript}\n\n[INSTRUCTION]\n{instruction}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log.info("HTTP server starting on port %d", args.port)
    app.run(host="127.0.0.1", port=args.port, threaded=True)
