# prodimopy_mcp/tools/notebooks.py
import json
import re
import shutil
from importlib import resources
from pathlib import Path

from mcp.types import ToolAnnotations

from prodimopy_mcp.server import mcp

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

_NB_PKG = "prodimopy_mcp.data"


def _notebooks_dir():
    return resources.files(_NB_PKG).joinpath("notebooks")


def _load_notebook(name: str) -> dict:
    """Load a bundled notebook by filename (with or without .ipynb extension)."""
    if not name.endswith(".ipynb"):
        name = name + ".ipynb"
    nb_file = _notebooks_dir().joinpath(name)
    return json.loads(nb_file.read_text(encoding="utf-8"))


def _notebook_description(nb: dict) -> str:
    """Extract a short description from the first markdown cell of a notebook."""
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "markdown":
            text = "".join(cell.get("source", []))
            # strip markdown headings and take first non-empty paragraph
            lines = [l.lstrip("#").strip() for l in text.splitlines() if l.strip()]
            if lines:
                return " ".join(lines[:3])  # first 3 lines max
    return ""


@mcp.tool(annotations=READ_ONLY)
def list_notebooks() -> list[dict]:
    """List all example notebooks bundled with prodimopy.

    Returns a list of available notebooks with their name and a short description
    extracted from the first markdown cell. Pass the ``name`` field to
    ``search_notebooks`` or ``open_notebook``.
    """
    results = []
    for entry in sorted(_notebooks_dir().iterdir()):
        if not entry.name.endswith(".ipynb"):
            continue
        try:
            nb = json.loads(entry.read_text(encoding="utf-8"))
            desc = _notebook_description(nb)
        except Exception:
            desc = ""
        results.append({"name": entry.name, "description": desc})
    return results


@mcp.tool(annotations=READ_ONLY)
def search_notebooks(
    query: str,
    cell_type: str | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Search prodimopy example notebooks for a regex pattern.

    Searches both markdown and code cells across all bundled notebooks and returns
    matching cells with surrounding context. Useful for finding code snippets, e.g.
    searching for ``'plot_sed'``, ``'read_prodimo'``, or ``'DataLine'``.

    Args:
        query: A regular expression (case-insensitive) to search for.
        cell_type: Restrict to ``'code'`` or ``'markdown'`` cells. If omitted,
            both types are searched.
        max_results: Maximum number of matching cells to return (default 20).
    """
    regex = re.compile(query, re.IGNORECASE)
    results = []
    for entry in sorted(_notebooks_dir().iterdir()):
        if not entry.name.endswith(".ipynb"):
            continue
        try:
            nb = json.loads(entry.read_text(encoding="utf-8"))
        except Exception:
            continue
        for cell_idx, cell in enumerate(nb.get("cells", []), start=1):
            ctype = cell.get("cell_type", "")
            if cell_type and ctype != cell_type:
                continue
            source = "".join(cell.get("source", []))
            if regex.search(source):
                # find lines containing the match for a focused snippet
                lines = source.splitlines()
                matching_lines = [
                    {"line": i + 1, "text": line}
                    for i, line in enumerate(lines)
                    if regex.search(line)
                ]
                results.append({
                    "notebook": entry.name,
                    "cell_number": cell_idx,
                    "cell_type": ctype,
                    "matching_lines": matching_lines,
                    "source": source,
                })
                if len(results) >= max_results:
                    return results
    return results


@mcp.tool()
def open_notebook(name: str, destination: str) -> str:
    """Copy a bundled prodimopy example notebook to a destination path.

    Use this when a user wants to adapt or run an example notebook locally.
    The notebook is copied from the bundled package data to the given path.

    Args:
        name: Notebook filename as returned by ``list_notebooks`` (e.g.
            ``'InspectModel.ipynb'``). The ``.ipynb`` extension is optional.
        destination: Absolute path where the notebook should be written,
            including filename (e.g. ``'/home/user/mywork/InspectModel.ipynb'``).

    Returns:
        The absolute path to the copied notebook.
    """
    if not name.endswith(".ipynb"):
        name = name + ".ipynb"
    nb_file = _notebooks_dir().joinpath(name)
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Use read/write via importlib.resources so this works with zip installs too
    content = nb_file.read_bytes()
    dest.write_bytes(content)
    return str(dest)
