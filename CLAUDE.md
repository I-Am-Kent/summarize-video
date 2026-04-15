# summarize-video — MCP Plugin

Claude plugin that downloads and transcribes videos from 1000+ platforms using local faster-whisper. No API keys required.

## Quick Reference

- **Language**: Python 3.11+
- **SDK**: fastmcp (via mcp[cli])
- **Transport**: stdio (launcher) → HTTP (processing server)
- **Tools**: 2 (`video_start`, `video_check`)
- **Pattern**: On-demand launcher — heavy server spawned on first tool call, freed after idle

## Commands

```bash
# Install dependencies
cd servers && uv sync

# Run launcher (stdio — for Claude Desktop/Code)
cd servers && uv run python launcher.py

# Inspect tools interactively
npx @modelcontextprotocol/inspector uv run --project servers python servers/launcher.py

# Run tests
cd servers && uv run pytest ../tests/

# Start HTTP server standalone (for debugging)
cd servers && uv run python video_http_server.py --port=9731 --idle-timeout=600 --model-size=base.en
```

## Architecture

```
summarize-video/
├── servers/
│   ├── launcher.py            Entry point — stdio MCP server, tool stubs, ensure_server()
│   ├── video_http_server.py   Heavy Flask server — yt-dlp, ffmpeg, faster-whisper
│   ├── pyproject.toml         All Python dependencies
│   └── tools/
│       ├── __init__.py        register_tools(mcp) — imports and registers all tools
│       ├── video_start.py     Start a job — forwards to POST /start
│       └── video_check.py     Poll job status — forwards to GET /check/{job_id}
├── skills/
│   ├── summarize-video/SKILL.md   /summarize-video:summarize <url>
│   └── transcribe-video/SKILL.md  /summarize-video:transcribe <url>
├── tests/                     Mirror of tools/ structure
├── docs/                      Architecture and adding-tools guides
├── .mcp.json                  MCP config for Cowork (uses ${CLAUDE_PLUGIN_ROOT})
└── .claude-plugin/            Plugin manifest and marketplace config
```

## Adding a New Tool

1. Create `servers/tools/{tool_name}.py` using the template in `docs/adding-tools.md`
2. Add import and registration in `servers/tools/__init__.py`
3. Create `tests/test_{tool_name}.py`
4. Run `cd servers && uv run pytest ../tests/`

## Critical Warnings

- **NEVER write to stdout in server code** — stdout is the stdio transport pipe. Use `log.info()` only.
- **NEVER import heavy packages at module level in launcher.py** — faster_whisper, yt_dlp, flask, imageio_ffmpeg must NOT appear at the top of launcher.py. Importing them triggers the 60s handshake timeout.
- **NEVER use subprocess.PIPE** — buffers fill and the process deadlocks. Always redirect to a file handle: `stdout=log_f, stderr=log_f`.
- **NEVER run Flask without threaded=True** — single-threaded Flask blocks /health during model load, causing the launcher's health-poll loop to time out.
- **All tool handlers in launcher must have top-level try/except** — unhandled exceptions crash the launcher process, silencing all tools for the session.
- **Claude Desktop has a 60s hardcoded timeout** — video_start/video_check use start/check polling for this reason. Do not add long-running logic directly to tool handlers.
- **HuggingFace is blocked in the Cowork VM** — Whisper model downloads happen on the host (via launcher), not inside a Co-Work skill's bash block.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | `9731` | Port for the Flask HTTP server |
| `IDLE_TIMEOUT` | `600` | Seconds before HTTP server self-terminates |
| `MODEL_SIZE` | `base.en` | faster-whisper model size (base.en, small.en, medium.en) |

## First-Run Timing

| Step | First run | Subsequent |
|------|-----------|------------|
| uv bootstrap | ~10s (skipped if installed) | 0s |
| Dep install | ~60-90s | 0s (cached venv) |
| Whisper model download | ~30-120s | 0s (cached in ~/.cache/summarize-video/models/) |
| Model load | ~5-15s (first call per session) | 0s (warm) |
| Idle RAM freed | After IDLE_TIMEOUT seconds | — |

## Log Files

All logs at `~/.cache/summarize-video/`:
- `launcher.log` — launcher process events
- `bootstrap.log` — uv install output
- `http_server.log` — Flask server events
- `ffmpeg.log` — ffmpeg stderr
