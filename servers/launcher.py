"""
launcher.py — Thin MCP server for summarize-video plugin.

This is the process registered with Claude Desktop / Cowork via .mcp.json.
It is intentionally lightweight (~5MB RAM) and completes the MCP handshake in <1s.

On the first tool call, ensure_server() spawns video_http_server.py (the heavy
Flask process with faster-whisper). The HTTP server self-terminates after IDLE_TIMEOUT
seconds of inactivity. If it crashes or exits, ensure_server() respawns it on the
next tool call — no Claude Desktop restart needed.

Critical: NO heavy imports at module level. faster_whisper, yt_dlp, flask, etc.
must NEVER appear in this file. Importing them here would trigger a 60-second
MCP handshake timeout on every Desktop open.
"""

import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import requests
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config from environment (set in .mcp.json)
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("SERVER_PORT", "9731"))
IDLE_TIMEOUT = int(os.environ.get("IDLE_TIMEOUT", "600"))
MODEL_SIZE = os.environ.get("MODEL_SIZE", "base.en")
BASE_URL = f"http://127.0.0.1:{PORT}"
STARTUP_WAIT = 120  # seconds to wait for HTTP server to become healthy

# ---------------------------------------------------------------------------
# Logging — NEVER write to stdout (it's the stdio transport pipe)
# ---------------------------------------------------------------------------
_log_dir = Path.home() / ".cache" / "summarize-video"
_log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(_log_dir / "launcher.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("launcher")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_proc: subprocess.Popen | None = None
_bootstrap_error: str | None = None
_server_script = Path(__file__).parent / "video_http_server.py"

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("summarize-video")

# When running as __main__, register this module as 'launcher' in sys.modules
# so that tools doing `from launcher import ensure_server` share this instance's
# state (_proc, _bootstrap_error) rather than importing a fresh copy.
if __name__ == "__main__":
    sys.modules.setdefault("launcher", sys.modules["__main__"])

# ---------------------------------------------------------------------------
# uv bootstrap — install uv if missing, then install deps
# ---------------------------------------------------------------------------

def _find_uv() -> str | None:
    import shutil
    found = shutil.which("uv")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "uv.exe",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _bootstrap_uv() -> str | None:
    if _find_uv():
        return None
    log.info("uv not found, installing...")
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command",
                 "irm https://astral.sh/uv/install.ps1 | iex"],
                check=True, capture_output=True,
            )
        else:
            import tempfile
            uv_installer = os.path.join(tempfile.gettempdir(), "uv-install.sh")
            urllib.request.urlretrieve("https://astral.sh/uv/install.sh", uv_installer)
            subprocess.run(["sh", uv_installer], check=True, capture_output=True)
        if _find_uv() is None:
            return ("ERROR: uv installer ran but uv not found. "
                    "Install manually: https://docs.astral.sh/uv/")
        log.info("uv installed successfully")
        return None
    except Exception as e:
        return (f"ERROR: Could not auto-install uv: {e}\n"
                "Install manually: https://docs.astral.sh/uv/")


def _bootstrap() -> None:
    global _bootstrap_error
    err = _bootstrap_uv()
    if err:
        _bootstrap_error = err
        log.error("Bootstrap failed: %s", err)
        return
    uv = _find_uv()
    project_dir = str(Path(__file__).parent)
    log_path = _log_dir / "bootstrap.log"
    log_f = open(str(log_path), "a", encoding="utf-8", errors="replace")
    try:
        result = subprocess.run(
            [uv, "sync", "--project", project_dir],
            stdout=log_f, stderr=log_f,
            timeout=300,
        )
        if result.returncode != 0:
            _bootstrap_error = (
                f"ERROR: 'uv sync' failed (exit {result.returncode}). "
                f"Check {log_path} for details."
            )
            log.error("uv sync failed: exit %d", result.returncode)
    except subprocess.TimeoutExpired:
        _bootstrap_error = "ERROR: Dependency installation timed out after 5 minutes."
        log.error("uv sync timed out")
    except Exception as e:
        _bootstrap_error = f"ERROR: Bootstrap exception: {e}"
        log.error("Bootstrap exception: %s", e)
    finally:
        log_f.close()


# ---------------------------------------------------------------------------
# HTTP server lifecycle
# ---------------------------------------------------------------------------

def _is_alive() -> bool:
    try:
        return requests.get(f"{BASE_URL}/health", timeout=1).status_code == 200
    except Exception:
        return False


def ensure_server() -> str | None:
    """Ensure the HTTP server is running. Returns None on success, error string on failure."""
    global _proc

    if _bootstrap_error:
        return _bootstrap_error

    if _is_alive():
        return None  # fast path

    log.info("Spawning video_http_server.py on port %d", PORT)

    # Kill zombie process if it exited without cleanup
    if _proc is not None and _proc.poll() is not None:
        log.info("Cleaning up dead server process (exit %d)", _proc.poll())
        _proc = None

    log_path = _log_dir / "http_server.log"
    log_f = open(str(log_path), "a", encoding="utf-8", errors="replace")

    uv = _find_uv()
    project_dir = str(Path(__file__).parent)

    _proc = subprocess.Popen(
        [
            uv, "run", "--project", project_dir,
            "python", str(_server_script),
            f"--port={PORT}",
            f"--idle-timeout={IDLE_TIMEOUT}",
            f"--model-size={MODEL_SIZE}",
        ],
        stdout=log_f,
        stderr=log_f,
    )

    deadline = time.time() + STARTUP_WAIT
    while time.time() < deadline:
        if _is_alive():
            log.info("HTTP server healthy on port %d", PORT)
            return None
        if _proc.poll() is not None:
            return (
                f"ERROR: HTTP server exited immediately (exit {_proc.poll()}). "
                f"Check {log_path} for details."
            )
        time.sleep(2)

    _proc.kill()
    _proc = None
    return (
        f"ERROR: HTTP server did not start within {STARTUP_WAIT}s. "
        f"Check {log_path} for details."
    )


# ---------------------------------------------------------------------------
# Tools are registered via tools/__init__.py
# ---------------------------------------------------------------------------
from tools import register_tools  # noqa: E402
register_tools(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    _bootstrap()
    mcp.run(transport="stdio")
