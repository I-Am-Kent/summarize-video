# Adding New Tools

Follow these steps to add a new MCP tool to the summarize-video plugin.

## Step 1: Create the tool file

Create `servers/tools/{tool_name}.py`:

```python
"""
Tool: {tool_name}
Purpose: {one-line description of what outcome this enables}
"""

import os
import requests

_BASE_URL = f"http://127.0.0.1:{os.environ.get('SERVER_PORT', '9731')}"


def {tool_name}(param1: str, param2: int = 10) -> str:
    """
    {Tool description — must answer:}

    WHEN to use: {specific scenario — when to use this vs. other tools}
    HOW to call: {parameter formatting guidance, types, constraints}
    WHAT returns: {shape and meaning of the response, possible statuses}

    Example: {concrete example of a good invocation and expected output}

    Do NOT use when: {negative examples}
    """
    try:
        from launcher import ensure_server  # noqa: PLC0415
        err = ensure_server()
        if err:
            return err

        # Validate inputs
        if not param1:
            return "ERROR: param1 is required."

        # Forward to HTTP server
        resp = requests.post(
            f"{_BASE_URL}/your-endpoint",
            json={"param1": param1, "param2": param2},
            timeout=290,
        )
        data = resp.json()
        return data.get("result") or f"ERROR: {data.get('error', 'empty response')}"

    except requests.ConnectionError:
        return "ERROR: Lost connection to processing server. Try again."
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
```

**Rules:**
- Always import `ensure_server` from `launcher` inside the function (not at module level)
- Always wrap the entire body in `try/except Exception as e` returning an error string
- Use `timeout=290` for calls that might take time, `timeout=30` for quick lookups
- Descriptions must be 50-300 words, answering WHEN/HOW/WHAT

## Step 2: Register the tool

Open `servers/tools/__init__.py` and add:

```python
from .{tool_name} import {tool_name}

def register_tools(mcp) -> None:
    mcp.tool()(video_start)
    mcp.tool()(video_check)
    mcp.tool()({tool_name})  # add this line
```

## Step 3: Add the HTTP endpoint (if needed)

If your tool needs new server-side logic, add a route to `servers/video_http_server.py`:

```python
@app.post("/your-endpoint")
def your_endpoint():
    global _last_call
    _last_call = time.time()

    body = request.get_json(silent=True) or {}
    param1 = body.get("param1", "").strip()

    if not param1:
        return jsonify({"error": "param1 is required"}), 400

    # Processing logic here
    result = do_something(param1)
    return jsonify({"result": result})
```

## Step 4: Write tests

Create `tests/test_{tool_name}.py`:

```python
"""Tests for {tool_name}."""
import pytest


def test_{tool_name}_returns_string(monkeypatch):
    """Tool always returns a string, even on error."""
    # Mock ensure_server and requests
    ...


def test_{tool_name}_invalid_input():
    """Tool rejects invalid inputs gracefully."""
    ...
```

## Step 5: Verify

```bash
# Run tests
cd servers && uv run pytest ../tests/

# Inspect interactively
npx @modelcontextprotocol/inspector uv run --project servers python servers/launcher.py
```
