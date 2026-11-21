"""Generate the prodimopy documentation and notebook data for prodimopy-mcp.

The script clones prodimopy at a pinned git ref (``[tool.prodimopy-mcp] prodimopy-ref``
in pyproject.toml), builds its Sphinx documentation and converts it to plain text.
The example notebooks are copied without their outputs. The result is written to
``src/prodimopy_mcp/data/`` (not tracked by git, but included in sdist and wheel).

The source is the local prodimopy repository (``$PRODIMOPY_SRC`` or ``../prodimopy``)
or any git URL, e.g. the prodimopy GitLab repository. Cloning from the local repository
uses the committed state of the ref; the working tree and its current branch are not
touched and uncommitted changes are not included.

Usage::

    python scripts/sync_data.py                       # local repo, pinned ref
    python scripts/sync_data.py --source https://gitlab.astro.rug.nl/prodimo/prodimopy.git
    python scripts/sync_data.py --ref master          # other branch or tag (development)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
DATA_DIR = ROOT / "src" / "prodimopy_mcp" / "data"
DOCS_OUT_DIR = DATA_DIR / "docs"
NB_OUT_DIR = DATA_DIR / "notebooks"
DEFAULT_SOURCE = ROOT.parent / "prodimopy"

DOC_DIRS = [".", "observables", "interface1D", "interface2D", "chemistry"]
EXCLUDE = {"api", "genindex", "search", "py-modindex"}  # skip autodoc-generated pages


def read_prodimopy_ref(pyproject: Path = PYPROJECT) -> str:
    """Return the pinned prodimopy git ref from ``[tool.prodimopy-mcp] prodimopy-ref``.

    Parameters
    ----------
    pyproject : Path
        Path to the pyproject.toml file.

    Returns
    -------
    str
        The git tag or branch, e.g. ``'v2.8.0'``.
    """
    with pyproject.open("rb") as f:
        return tomllib.load(f)["tool"]["prodimopy-mcp"]["prodimopy-ref"]


def get_base_url(rtd_version: str = "stable") -> str:
    """Return the base URL of the prodimopy documentation on Read the Docs.

    Parameters
    ----------
    rtd_version : str
        Either ``'stable'`` or ``'latest'``.

    Returns
    -------
    str
        The base URL, ending with a slash.
    """
    if rtd_version not in ("latest", "stable"):
        raise ValueError(f"Invalid version: {rtd_version}. Must be 'latest' or 'stable'.")
    return f"https://prodimopy.readthedocs.io/en/{rtd_version}/"


def source_to_url(source: str) -> str:
    """Convert the ``--source`` argument to a URL that ``git clone`` accepts.

    A git URL is returned unchanged. A local path is converted to a ``file://`` URL,
    so that ``git clone --depth 1`` also works for local repositories.

    Parameters
    ----------
    source : str
        A git URL or the path to a local prodimopy repository.

    Returns
    -------
    str
        The URL for ``git clone``.

    Raises
    ------
    FileNotFoundError
        If ``source`` is a local path that does not exist.
    """
    if "://" in source or source.startswith("git@"):
        return source
    path = Path(source).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"prodimopy repository not found: {path} (set PRODIMOPY_SRC or use --source)")
    return path.as_uri()


def clone_prodimopy(source_url: str, ref: str, dest: Path) -> None:
    """Clone prodimopy at ``ref`` (tag or branch) into ``dest`` (shallow clone).

    Parameters
    ----------
    source_url : str
        URL of the prodimopy repository (see :func:`source_to_url`).
    ref : str
        Git tag or branch.
    dest : Path
        Target directory; it must not exist yet.

    Raises
    ------
    SystemExit
        If ``git clone`` fails, e.g. because the ref does not exist.
    """
    cmd = ["git", "clone", "--quiet", "--depth", "1", "--branch", ref, source_url, str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"git clone of prodimopy at '{ref}' from {source_url} failed:\n{result.stderr.strip()}\n"
            "If the tag is missing in a local repository, run 'git fetch --tags' there."
        )


def build_docs(src: Path) -> Path:
    """Build the HTML documentation of a prodimopy clone with Sphinx.

    Uses the same options as prodimopy's docs/Makefile (``-T -E``).

    Parameters
    ----------
    src : Path
        Root directory of the prodimopy clone.

    Returns
    -------
    Path
        The directory with the built HTML pages.
    """
    docs = src / "docs"
    cmd = [sys.executable, "-m", "sphinx", "-M", "html", ".", "_build", "-T", "-E", "-q"]
    subprocess.run(cmd, cwd=docs, check=True)
    return docs / "_build" / "html"


def check_installed_version(ref: str) -> None:
    """Warn if the installed prodimopy version does not match a version tag ``ref``.

    The docs build reads the version string from the installed prodimopy, and the
    MCP server inspects the installed prodimopy. Branch names are not checked.

    Parameters
    ----------
    ref : str
        Git tag or branch, e.g. ``'v2.8.0'``.
    """
    if not re.fullmatch(r"v?\d+(\.\d+)*", ref):
        return
    try:
        installed = version("prodimopy")
    except PackageNotFoundError:
        warnings.warn("prodimopy is not installed in this environment.", stacklevel=2)
        return
    if installed != ref.removeprefix("v"):
        warnings.warn(
            f"Installed prodimopy {installed} does not match prodimopy-ref {ref}. "
            "Run 'pixi update prodimopy' or adapt prodimopy-ref.",
            stacklevel=2,
        )


def html_to_text(html: str) -> str:
    """Extract the main text of a Sphinx HTML page.

    Images are replaced by ``[figure: <alt text>]``; navigation, scripts and styles
    are removed.

    Parameters
    ----------
    html : str
        The HTML page.

    Returns
    -------
    str
        The text, one element per line.
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", {"role": "main"}) or soup.find("main") or soup
    for img in content.find_all("img"):
        img.replace_with(f"[figure: {img.get('alt', '')}]")
    for tag in content.find_all(["nav", "script", "style"]):
        tag.decompose()
    return content.get_text(separator="\n", strip=True)


def strip_notebook_outputs(nb: dict) -> dict:
    """Return a copy of a notebook without outputs, execution counts and cell metadata.

    Parameters
    ----------
    nb : dict
        The notebook as loaded from JSON.

    Returns
    -------
    dict
        The stripped copy; ``nb`` is not changed.
    """
    nb = json.loads(json.dumps(nb))  # deep copy
    for cell in nb.get("cells", []):
        cell.pop("outputs", None)
        cell.pop("execution_count", None)
        cell["metadata"] = {}
    nb.get("metadata", {}).pop("widgets", None)
    return nb


def clear_generated(out_dir: Path, patterns: list[str]) -> None:
    """Delete previously generated files that match ``patterns`` in ``out_dir``.

    Parameters
    ----------
    out_dir : Path
        Output directory; it is created if it does not exist.
    patterns : list[str]
        Glob patterns of the generated files, e.g. ``['*.txt']``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in patterns:
        for path in out_dir.glob(pattern):
            path.unlink()


def write_docs(html_dir: Path, out_dir: Path, base_url: str, ref: str) -> int:
    """Convert the HTML pages to text files and write ``manifest.json``.

    Parameters
    ----------
    html_dir : Path
        Directory with the built HTML documentation.
    out_dir : Path
        Output directory for the text files and the manifest.
    base_url : str
        Read the Docs base URL for the links in the manifest.
    ref : str
        The prodimopy git ref, stored in the manifest.

    Returns
    -------
    int
        Number of written pages.
    """
    clear_generated(out_dir, ["*.txt", "manifest.json"])
    manifest: dict = {"prodimopy_ref": ref, "docs": []}
    for doc_dir in DOC_DIRS:
        for html_file in sorted((html_dir / doc_dir).glob("*.html")):
            rel = html_file.relative_to(html_dir)
            if rel.stem in EXCLUDE or rel.parts[0] in EXCLUDE:
                continue
            html = html_file.read_text(encoding="utf-8")
            out_name = rel.with_suffix(".txt").name
            (out_dir / out_name).write_text(html_to_text(html), encoding="utf-8")
            title_tag = BeautifulSoup(html, "html.parser").find("h1")
            manifest["docs"].append(
                {
                    "file": out_name,
                    "title": title_tag.get_text(strip=True) if title_tag else rel.stem,
                    "url": base_url + rel.as_posix(),
                }
            )
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return len(manifest["docs"])


def write_notebooks(nb_src_dir: Path, out_dir: Path) -> int:
    """Copy the example notebooks without outputs.

    Parameters
    ----------
    nb_src_dir : Path
        Directory with the prodimopy example notebooks (``docs/notebooks``).
    out_dir : Path
        Output directory.

    Returns
    -------
    int
        Number of written notebooks.
    """
    clear_generated(out_dir, ["*.ipynb"])
    count = 0
    for nb_path in sorted(nb_src_dir.glob("*.ipynb")):
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        (out_dir / nb_path.name).write_text(
            json.dumps(strip_notebook_outputs(nb), indent=1, ensure_ascii=False), encoding="utf-8"
        )
        count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    """Run the data sync (command line entry point).

    Parameters
    ----------
    argv : list[str] or None
        Command line arguments; ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source",
        default=os.environ.get("PRODIMOPY_SRC", str(DEFAULT_SOURCE)),
        help="local prodimopy repository or git URL (default: $PRODIMOPY_SRC or ../prodimopy)",
    )
    parser.add_argument("--ref", default=None, help="git tag or branch (default: prodimopy-ref in pyproject.toml)")
    parser.add_argument(
        "--rtd-version",
        choices=["stable", "latest"],
        default="stable",
        help="Read the Docs version used for the links (default: stable)",
    )
    args = parser.parse_args(argv)

    ref = args.ref or read_prodimopy_ref()
    source_url = source_to_url(args.source)
    check_installed_version(ref)

    with tempfile.TemporaryDirectory(prefix="prodimopy-src-") as tmp:
        src = Path(tmp) / "prodimopy"
        print(f"Cloning prodimopy {ref} from {source_url} ...")
        clone_prodimopy(source_url, ref, src)
        print("Building the prodimopy documentation ...")
        html_dir = build_docs(src)
        n_docs = write_docs(html_dir, DOCS_OUT_DIR, get_base_url(args.rtd_version), ref)
        n_nbs = write_notebooks(src / "docs" / "notebooks", NB_OUT_DIR)

    print(f"Wrote {n_docs} documentation pages to {DOCS_OUT_DIR.relative_to(ROOT)}")
    print(f"Wrote {n_nbs} notebooks to {NB_OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
