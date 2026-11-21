"""Tests for the MCP tool functions, called directly (without an MCP client)."""

from importlib import resources

import pytest

from prodimopy_mcp.tools import introspection, knowledge, notebooks

DATA_SYNCED = resources.files("prodimopy_mcp.data").joinpath("docs/manifest.json").is_file()
needs_data = pytest.mark.skipif(not DATA_SYNCED, reason="data not generated (run: pixi run sync-data)")


def test_list_read_functions_finds_read_prodimo() -> None:
    """The installed prodimopy provides ``read_prodimo`` in the disk read module."""
    names = [entry["name"] for entry in introspection.list_read_functions(module="read_disk")]
    assert "read_prodimo" in names


def test_describe_function_returns_docstring() -> None:
    """``describe_function`` returns the signature and docstring of a prodimopy function."""
    result = introspection.describe_function("read_prodimo", module="read_disk")
    assert result is not None
    assert result["doc"]


@needs_data
def test_search_docs_finds_pages() -> None:
    """``search_docs`` finds documentation pages and returns their URLs."""
    results = knowledge.search_docs("plot", max_results=2)
    assert 0 < len(results) <= 2
    assert all(r["url"].startswith("https://prodimopy.readthedocs.io/") for r in results)


@needs_data
def test_list_notebooks_returns_bundled_notebooks() -> None:
    """``list_notebooks`` lists the bundled example notebooks."""
    assert len(notebooks.list_notebooks()) > 0
