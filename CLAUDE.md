# summarize-video

## Purpose

Claude plugin that transcribes and summarises videos from YouTube, TikTok, Instagram, and 1000+ other platforms — entirely locally, with no API keys. Built because cloud transcription services cost money and require sharing video data with third parties. faster-whisper runs on CPU so it works on any machine without a GPU.

## Tech Stack

- Python 3.11+, FastMCP (mcp[cli]), Flask, yt-dlp, faster-whisper, imageio-ffmpeg
- Two-process architecture: thin stdio launcher + on-demand Flask HTTP server
- Plugin packaging: `.claude-plugin/`, `.mcp.json`, `skills/`

## Commands

```bash
# Install
cd servers && uv sync

# Run launcher (stdio — Claude Desktop/Code)
cd servers && uv run python launcher.py

# Debug HTTP server standalone
cd servers && uv run python video_http_server.py --port=9731 --idle-timeout=600 --model-size=base.en

# Test
cd servers && uv run pytest ../tests/

# Inspect tools interactively
npx @modelcontextprotocol/inspector uv run --project servers python servers/launcher.py
```

## Architecture

```
servers/
  launcher.py           Thin stdio MCP server — ensure_server(), tool registration only
  video_http_server.py  Heavy Flask server — yt-dlp download, ffmpeg, faster-whisper
  tools/
    __init__.py         register_tools(mcp) — add new tools here
    video_start.py      Forwards POST /start → returns job_id
    video_check.py      Forwards GET /check/{job_id} → returns status/result
skills/
  summarize-video/      /summarize-video:summarize <url>
  transcribe-video/     /summarize-video:transcribe <url>
.mcp.json               Cowork delivery — uses ${CLAUDE_PLUGIN_ROOT}
.claude-plugin/         plugin.json + marketplace.json
```

## Adding a Tool

1. `servers/tools/{name}.py` — follow template in `docs/adding-tools.md`
2. Register in `servers/tools/__init__.py`
3. Add `tests/test_{name}.py`
4. `cd servers && uv run pytest ../tests/`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | `9731` | Flask HTTP server port |
| `IDLE_TIMEOUT` | `600` | Seconds before HTTP server self-terminates |
| `MODEL_SIZE` | `base.en` | faster-whisper model (base.en / small.en / medium.en) |

## Gotchas

- **Never import heavy packages at module level in `launcher.py`** — `faster_whisper`, `yt_dlp`, `flask`, `imageio_ffmpeg` at the top of launcher triggers the 60s MCP handshake timeout on every Desktop open. Keep them lazy (inside functions).
- **Never write to stdout in any server code** — stdout is the stdio transport pipe. `log.info()` only.
- **Never use `subprocess.PIPE`** — pipe buffers fill and deadlock. Always pass a real file handle: `stdout=log_f, stderr=log_f`.
- **Flask must have `threaded=True`** — without it, `/health` blocks during model load and the launcher's startup poll times out.
- **Claude Desktop has a 60s hardcoded tool timeout** — that's why `video_start`/`video_check` use the start/check polling pattern. Don't put long-running logic directly in tool handlers.
- **All tool handlers need top-level `try/except`** — unhandled exceptions crash the launcher process, silencing all tools for the session.
- **HuggingFace is blocked in the Cowork VM** — model downloads happen on the host (launcher spawns HTTP server which downloads on first use). Run one local transcription before using Cowork to pre-cache the model.
- **`sys.modules['launcher']` alias** — set in `launcher.py` so tools can `from launcher import ensure_server` even when the module runs as `__main__`. Don't remove it.
- **Windows ARM64**: `imageio-ffmpeg` has no pre-built binary for this platform — system ffmpeg required (`winget install ffmpeg`).

## First-Run Timing

| Step | First run | Subsequent |
|------|-----------|------------|
| uv dep install | ~60-90s | 0s (cached) |
| Whisper model download | ~30-120s | 0s (cached at `~/.cache/summarize-video/models/`) |
| Model load | ~5-15s | 0s (warm for session) |

Logs at `~/.cache/summarize-video/`: `launcher.log`, `bootstrap.log`, `http_server.log`, `ffmpeg.log`
