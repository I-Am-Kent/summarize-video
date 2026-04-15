"""
tools/__init__.py — Auto-registers all MCP tools onto the FastMCP instance.

To add a new tool:
1. Create tools/{tool_name}.py following the template in docs/adding-tools.md
2. Import and register the function here
"""

from .video_check import video_check
from .video_start import video_start


def register_tools(mcp) -> None:
    """Register all tools on the FastMCP instance."""
    mcp.tool()(video_start)
    mcp.tool()(video_check)
