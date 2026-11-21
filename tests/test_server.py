"""Tests for the prodimopy MCP server (``prodimopy-mcp``).

The tests connect an MCP client in-process to the server, so no subprocess is started.
"""

import asyncio

from mcp import Client
from mcp.types import TextContent

from prodimopy_mcp.server import mcp as prodimopy_mcp_server

EXPECTED_TOOLS = {
    "ping",
    "list_read_functions",
    "list_plot_functions",
    "describe_function",
    "search_source",
    "search_docs",
    "list_notebooks",
    "search_notebooks",
    "open_notebook",
}


async def _list_tool_names() -> list[str]:
    """Return the names of all tools the server provides."""
    async with Client(prodimopy_mcp_server) as client:
        result = await client.list_tools()
        return [tool.name for tool in result.tools]


async def _call_ping() -> str:
    """Call the ``ping`` tool and return its text output."""
    async with Client(prodimopy_mcp_server) as client:
        result = await client.call_tool("ping", {})
        assert not result.is_error, f"ping returned an error: {result.content}"
        content = result.content[0]
        assert isinstance(content, TextContent)
        return content.text


def test_all_tools_are_listed() -> None:
    """The server lists all expected tools."""
    assert EXPECTED_TOOLS <= set(asyncio.run(_list_tool_names()))


def test_ping() -> None:
    """The ``ping`` tool returns the expected answer."""
    assert asyncio.run(_call_ping()) == "pong from prodimopy-mcp"
