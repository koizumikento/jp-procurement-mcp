from mcp.server import MCPServer

from procurement_awards_mcp import server as awards_server
from procurement_notices_mcp import server as notices_server


def create_server() -> MCPServer:
    mcp = MCPServer("jp-procurement-mcp")
    mcp.tool(annotations=notices_server.READ_ONLY)(
        notices_server._tool_errors(notices_server.search_notices)
    )
    mcp.tool(annotations=awards_server.READ_ONLY)(awards_server.search_awards)
    mcp.tool(annotations=awards_server.READ_ONLY)(awards_server.summarize_awards)
    return mcp
