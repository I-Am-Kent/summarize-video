# Architecture

## Why Two Processes?

Claude Desktop enforces a hardcoded 60-second timeout on the MCP initialization handshake. The `faster-whisper` library takes 5-15 seconds to import (CUDA scan + model init) and ~850MB of RAM once loaded.

A single-process stdio server would:
1. Take too long to start on first use (timeout risk)
2. Hold ~850MB RAM from Desktop open to Desktop quit
3. Have no crash recovery — if the server dies, tools go silent until Desktop restarts

The on-demand launcher pattern solves all three:

```
launcher.py (~5MB, always running)
    ↓ first tool call
video_http_server.py (~850MB, only when needed)
    ↓ idle for IDLE_TIMEOUT seconds
(process exits, RAM freed)
    ↓ next tool call
video_http_server.py (respawned)
```

## The 60-Second Timeout and Polling Pattern

Claude Desktop also has a hardcoded 60-second timeout on individual tool calls. Video processing (download + transcription) takes 1-5 minutes. 

`video_start` returns immediately with a job_id. `video_check` polls for completion. Claude polls every 15-20 seconds. This works within the 60s constraint because each individual tool call completes quickly.

Progress notifications do NOT reset the timer in Claude Desktop (this is a confirmed limitation, not a feature gap). The polling pattern is the correct solution.

## yt-dlp Platform Support

yt-dlp supports 1000+ platforms natively. No platform-specific code is needed — yt-dlp detects the extractor from the URL automatically. Instagram, TikTok, Twitter/X, Vimeo, Reddit, and many others work out of the box.

The only notable exception is platforms requiring authentication (private Instagram posts, paywalled content). These would require cookie configuration, which is out of scope for this plugin.

## ffmpeg Strategy

ffmpeg is required for audio extraction. The plugin uses a two-tier approach:

1. **System ffmpeg** (preferred): `shutil.which("ffmpeg")` — uses whatever the user has installed
2. **imageio-ffmpeg** (fallback): Ships a pre-built static binary for macOS ARM64, macOS x64, Windows x64, Linux x64 — zero-setup for users without system ffmpeg

This means the plugin works out-of-the-box on a clean machine without requiring the user to install ffmpeg manually.

## Model Caching

The Whisper model (~140MB for base.en) is downloaded once and cached at:
`~/.cache/summarize-video/models/`

The `CLAUDE_PLUGIN_DATA` environment variable (set by the plugin runtime in Cowork) is also supported for persistent cross-session storage in managed environments.

## Co-Work Compatibility

Co-Work VMs run Ubuntu 22.04 ARM64 with a network allowlist (HuggingFace is blocked). Two constraints affect this plugin:

1. **Model downloads must happen on the host** — the launcher handles this when the HTTP server first loads the model. Users should run at least one local transcription before using Co-Work to ensure the model is cached.

2. **MCP tools reach the VM via plugin .mcp.json** — the `${CLAUDE_PLUGIN_ROOT}` variable is resolved to the plugin's install path. The `claude_desktop_config.json` SDK bridge is unreliable and not used.

Skills detect the Co-Work environment via `$CLAUDE_CODE_IS_COWORK` env var and adapt accordingly.
