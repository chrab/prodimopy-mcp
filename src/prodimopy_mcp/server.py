# prodimopy_mcp/server.py
from mcp.server.mcpserver import MCPServer
mcp = MCPServer("prodimopy")

from prodimopy_mcp.tools import introspection  # noqa: E402,F401
from prodimopy_mcp.tools import knowledge  # noqa: E402,F401
from prodimopy_mcp.tools import notebooks  # noqa: E402,F401

@mcp.tool()
def ping() -> str:
    """Check that the prodimopy MCP server is running."""
    return "pong from prodimopy-mcp"

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()