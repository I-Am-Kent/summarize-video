---
name: summarize-video
description: Summarize a video from YouTube, Instagram, TikTok, Vimeo, Twitter/X, or any yt-dlp supported platform. Returns key points, main ideas, and conclusion.
argument-hint: <video-url>
allowed-tools: [Bash, Read]
---

Summarize the video at the provided URL.

1. Detect environment:
   - Run: `test -n "$CLAUDE_CODE_IS_COWORK" && echo "cowork" || echo "local"`
   - If "cowork": follow the Co-Work path below.
   - Otherwise: follow the Local path.

## Local path (Claude Desktop / Claude Code)

Use the `video_start` MCP tool with mode="summary":

```
video_start(url="<url>", mode="summary")
```

Then poll with `video_check` every 15-20 seconds until status is "complete" or "failed":

```
video_check(job_id="<job_id_from_start>")
```

When complete, present the transcript to the user and act on the [INSTRUCTION] section by generating a concise summary.

## Co-Work path (remote VM)

Co-Work VMs don't have direct access to MCP tools from the host. Use the CLI instead.

Find the plugin root:
```bash
PLUGIN_ROOT=$(find /sessions -name "launcher.py" -path "*/summarize-video*" 2>/dev/null | head -1 | xargs dirname)
```

Install dependencies:
```bash
cd "$PLUGIN_ROOT" && uv sync --project . 2>&1 | tail -5
```

Download and transcribe:
```bash
cd "$PLUGIN_ROOT" && uv run python video_http_server.py --help
```

Note: Co-Work VMs block HuggingFace. If the Whisper model has not been downloaded on the host first, model download will fail inside the VM. Ask the user to run a local transcription first to cache the model.

When the transcript is available, summarize it: identify the main topic, key arguments, examples used, and conclusion.
