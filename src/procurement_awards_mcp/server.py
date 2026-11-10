from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .client import search_awards, summarize_awards

READ_ONLY = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, destructive_hint=False, open_world_hint=True
)


def create_server() -> MCPServer:
    mcp = MCPServer("procurement-awards-mcp")
    mcp.tool(annotations=READ_ONLY)(search_awards)
    mcp.tool(annotations=READ_ONLY)(summarize_awards)
    return mcp
