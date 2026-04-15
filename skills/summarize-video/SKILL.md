---
name: summarize-video
description: Summarize a video from YouTube, Instagram, TikTok, Vimeo, Twitter/X, or any yt-dlp supported platform. Returns key points, main ideas, and conclusion.
argument-hint: <video-url>
allowed-tools: [Bash, Read]
---

Summarize the video at the provided URL.

## How to use

Use the `video_start` MCP tool with mode="summary", then poll with `video_check` following the interval each response tells you:

```
video_start(url="<url>", mode="summary")
```

Then call `video_check` in 5 seconds, then keep polling at the interval the response tells you:

```
video_check(job_id="<job_id_from_start>")
```

When complete, present the transcript to the user and act on the [INSTRUCTION] section by generating a concise summary.

## Cowork environment notes

In Cowork, the MCP tools route to the **host Mac** via LocalMcpServerManager — they do NOT run inside the VM. This means yt-dlp downloads happen on the host with full internet access, and YouTube/TikTok/Instagram CDNs are all reachable.

The CLI path (running `video_http_server.py` directly inside the VM) does **not** work in Cowork due to multiple VM network restrictions:
- YouTube and video CDNs are blocked by the VM proxy
- GitHub is blocked (`uv sync` cannot download Python or packages)
- HuggingFace is blocked (Whisper model downloads fail)

**Do not attempt the CLI path in Cowork.** Use the MCP tools directly — they already run on the host.

If `video_start` returns an error about the server not being available, it means the `summarize-video` server is not registered in the user's `claude_desktop_config.json`. Ask the user to add it.
