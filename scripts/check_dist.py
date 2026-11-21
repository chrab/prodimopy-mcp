"""Check that the generated data is included in the sdist and the wheel in ``dist/``.

The data in ``src/prodimopy_mcp/data/`` is not tracked by git, so it only gets into
the packages via MANIFEST.in (sdist) and package-data (wheel). This check makes sure
that a release never ships without it.
"""

import sys
import tarfile
import zipfile
from pathlib import Path

DIST = Path(__file__).resolve().parent.parent / "dist"
DATA_PREFIX = "prodimopy_mcp/data/"


def data_files(names: list[str]) -> dict[str, int]:
    """Count the data files in a list of archive member names.

    Parameters
    ----------
    names : list[str]
        Member names of an sdist or wheel.

    Returns
    -------
    dict[str, int]
        Counts for ``'manifest'``, ``'docs'`` (text pages) and ``'notebooks'``.
    """
    data = [n.split(DATA_PREFIX, 1)[1] for n in names if DATA_PREFIX in n]
    return {
        "manifest": sum(1 for n in data if n == "docs/manifest.json"),
        "docs": sum(1 for n in data if n.startswith("docs/") and n.endswith(".txt")),
        "notebooks": sum(1 for n in data if n.startswith("notebooks/") and n.endswith(".ipynb")),
    }


def main() -> int:
    """Check all sdists and wheels in ``dist/``.

    Returns
    -------
    int
        0 if every package contains the manifest, text pages and notebooks, else 1.
    """
    packages = sorted(DIST.glob("*.tar.gz")) + sorted(DIST.glob("*.whl"))
    if not packages:
        print(f"No packages found in {DIST}")
        return 1
    ok = True
    for package in packages:
        if package.suffix == ".whl":
            with zipfile.ZipFile(package) as zf:
                counts = data_files(zf.namelist())
        else:
            with tarfile.open(package) as tf:
                counts = data_files(tf.getnames())
        good = counts["manifest"] == 1 and counts["docs"] > 0 and counts["notebooks"] > 0
        ok &= good
        print(f"{'PASSED' if good else 'FAILED'} {package.name}: {counts}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
