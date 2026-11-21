"""Tests for the helper functions of ``scripts/sync_data.py``."""

from pathlib import Path

import pytest

import sync_data


def test_html_to_text_uses_main_content() -> None:
    """Only the main content is kept; scripts are removed and images are replaced."""
    html = (
        "<html><body><nav>Menu</nav>"
        '<div role="main"><h1>Title</h1><script>var x = 1;</script>'
        '<img alt="A plot"><p>Body text</p></div></body></html>'
    )
    text = sync_data.html_to_text(html)
    assert text.splitlines() == ["Title", "[figure: A plot]", "Body text"]


def test_strip_notebook_outputs() -> None:
    """Outputs, execution counts and cell metadata are removed; the input is unchanged."""
    nb = {
        "cells": [{"cell_type": "code", "source": ["1+1"], "outputs": [{"x": 1}], "execution_count": 3, "metadata": {"a": 1}}],
        "metadata": {"widgets": {}, "kernelspec": {}},
    }
    stripped = sync_data.strip_notebook_outputs(nb)
    assert stripped["cells"][0] == {"cell_type": "code", "source": ["1+1"], "metadata": {}}
    assert "widgets" not in stripped["metadata"]
    assert "outputs" in nb["cells"][0]


def test_read_prodimopy_ref(tmp_path: Path) -> None:
    """The pinned ref is read from ``[tool.prodimopy-mcp]``."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.prodimopy-mcp]\nprodimopy-ref = "v9.9.9"\n')
    assert sync_data.read_prodimopy_ref(pyproject) == "v9.9.9"


def test_project_pins_a_prodimopy_ref() -> None:
    """The project's pyproject.toml defines a prodimopy-ref."""
    assert sync_data.read_prodimopy_ref()


def test_source_to_url(tmp_path: Path) -> None:
    """Git URLs stay unchanged, local paths become file:// URLs."""
    url = "https://gitlab.astro.rug.nl/prodimo/prodimopy.git"
    assert sync_data.source_to_url(url) == url
    assert sync_data.source_to_url(str(tmp_path)) == tmp_path.resolve().as_uri()


def test_source_to_url_missing_path(tmp_path: Path) -> None:
    """A missing local repository gives a clear error."""
    with pytest.raises(FileNotFoundError, match="PRODIMOPY_SRC"):
        sync_data.source_to_url(str(tmp_path / "missing"))


def test_get_base_url() -> None:
    """Only 'stable' and 'latest' are valid Read the Docs versions."""
    assert sync_data.get_base_url("stable") == "https://prodimopy.readthedocs.io/en/stable/"
    with pytest.raises(ValueError):
        sync_data.get_base_url("v2.8.0")
