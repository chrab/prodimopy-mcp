# prodimopy_mcp/tools/knowledge.py
import json
from importlib import resources
from mcp.types import ToolAnnotations
from prodimopy_mcp.server import mcp

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

_DATA_PKG = "prodimopy_mcp.data"


def _load_manifest() -> dict:
    with resources.files(_DATA_PKG).joinpath("docs/manifest.json").open("r") as f:
        return json.load(f)


@mcp.tool(annotations=READ_ONLY)
def search_docs(query: str, max_results: int = 3) -> list[dict]:
    """Search prodimopy documentation pages for a query string, returning the
    best-matching pages with a short snippet and a link to the readthedocs page."""
    docs_dir = resources.files(_DATA_PKG).joinpath("docs")
    manifest = _load_manifest()
    url_by_file = {entry["file"]: entry["url"] for entry in manifest.get("docs", [])}
    title_by_file = {entry["file"]: entry.get("title", "") for entry in manifest.get("docs", [])}
    terms = query.lower().split()
    scored = []
    for entry in docs_dir.iterdir():
        if not entry.name.endswith((".md", ".rst", ".txt")):
            continue
        text = entry.read_text()
        lower = text.lower()
        body_score = sum(lower.count(t) for t in terms)
        # Boost when terms match the filename (stem) or title — these are strong signals.
        # Each matching term contributes, and a multiplier rewards pages where *all*
        # query terms are found in the filename/title (i.e. the page is a direct match).
        stem = entry.name.rsplit(".", 1)[0].lower()
        title = title_by_file.get(entry.name, "").lower()
        matched_terms = sum(1 for t in terms if t in stem or t in title)
        title_boost = matched_terms * 200 * matched_terms  # quadratic: 1→200, 2→800, 3→1800
        score = body_score + title_boost
        if score > 0:
            idx = lower.find(terms[0])
            snippet = text[max(0, idx - 100): idx + 200]
            scored.append({
                "page": entry.name,
                "score": score,
                "snippet": snippet,
                "url": url_by_file.get(entry.name, ""),
            })
    scored.sort(key=lambda r: -r["score"])
    return scored[:max_results]