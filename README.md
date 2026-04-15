# summarize-video

A Claude plugin that downloads and transcribes videos from YouTube, Instagram, TikTok, Vimeo, Twitter/X, and 1000+ other platforms using local AI. **No API keys required.**

## What it does

- Downloads videos from any [yt-dlp supported platform](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- Transcribes audio locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (base.en model, ~140MB)
- Returns output in your chosen format: raw transcript, summary, key points, or action items
- Works in Claude Desktop (Chat tab) and Claude Cowork

## Tools

| Tool | Description |
|------|-------------|
| `video_start(url, mode)` | Start a download + transcription job (returns immediately with job_id) |
| `video_check(job_id)` | Poll job status — call every 15-20 seconds until complete |

**Output modes for `video_start`:**

| Mode | Output |
|------|--------|
| `summary` (default) | Transcript + instruction to summarize |
| `transcript` | Raw verbatim transcript only |
| `key_points` | Transcript + instruction to extract key points |
| `action_items` | Transcript + instruction to extract action items |

## Skills

| Skill | Command |
|-------|---------|
| Summarize a video | `/summarize-video:summarize <url>` |
| Transcribe a video | `/summarize-video:transcribe <url>` |

## Installation

Install via the Claude plugin marketplace or by adding this repository as a custom marketplace.

## Claude Desktop Configuration (Chat tab)

After installing the plugin, find the install path under `~/.claude/plugins/cache/` and add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "summarize-video": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/Users/YOUR_USERNAME/.claude/plugins/cache/summarize-video@.../servers",
        "python",
        "/Users/YOUR_USERNAME/.claude/plugins/cache/summarize-video@.../servers/launcher.py"
      ],
      "env": {
        "SERVER_PORT": "9731",
        "IDLE_TIMEOUT": "600",
        "MODEL_SIZE": "base.en"
      }
    }
  }
}
```

Replace the paths with your actual plugin install path (check `~/.claude/plugins/installed_plugins.json` for the exact path after installation).

## First-Run Expectations

The first time you use this plugin:

| Step | Time |
|------|------|
| Dependency installation (uv sync) | ~60-90 seconds |
| Whisper model download (~140MB) | ~30-120 seconds depending on connection |
| Model load on first transcription | ~5-15 seconds |

Subsequent uses start in seconds (deps and model are cached).

## Platform Support

| Platform | Supported | Notes |
|----------|-----------|-------|
| macOS (Apple Silicon) | ✓ | Fully supported |
| macOS (Intel) | ✓ | Fully supported |
| Windows x64 | ✓ | Fully supported |
| Windows ARM64 | ⚠ | Requires system ffmpeg — `imageio-ffmpeg` has no ARM64 binary. Install via `winget install ffmpeg`. |
| Linux x64 | ✓ | Fully supported |

## Model Options

Change `MODEL_SIZE` in the config to trade accuracy vs. speed:

| Model | RAM | Speed | Accuracy |
|-------|-----|-------|---------|
| `tiny.en` | ~200MB | Fastest | Lower |
| `base.en` (default) | ~300MB | Fast | Good |
| `small.en` | ~500MB | Moderate | Better |
| `medium.en` | ~1.5GB | Slow | Best |

## Log Files

Logs are at `~/.cache/summarize-video/`:
- `launcher.log` — launcher events
- `bootstrap.log` — dependency install output
- `http_server.log` — processing server events
- `ffmpeg.log` — audio extraction output

## Troubleshooting

**Plugin tools don't appear in Claude Desktop**
1. Check `~/.cache/summarize-video/launcher.log` for errors
2. Ensure `uv` is installed: `which uv` or install from https://docs.astral.sh/uv/
3. Verify the `claude_desktop_config.json` path is correct

**Transcription is slow or fails**
- First run downloads the model — wait up to 2 minutes
- Check `~/.cache/summarize-video/http_server.log` for errors
- Try a shorter video first to verify the pipeline works

**Co-Work VM: model download fails**
- HuggingFace is blocked in the Co-Work VM network
- Run a local transcription first (via Claude Desktop) to cache the model at `~/.cache/summarize-video/models/`

**ffmpeg not found**
- The plugin includes a bundled ffmpeg binary via `imageio-ffmpeg` as a fallback
- If that fails, install system ffmpeg: `brew install ffmpeg` (macOS) or `winget install ffmpeg` (Windows)
