import inspect
import re
from pathlib import Path
from prodimopy import read as read_disk_module
from prodimopy import read_mc as read_mc_module
from prodimopy import read_slab as read_slab_module
from prodimopy.observables import read_casasim as read_casasim_module

from prodimopy import plot as plot_disk_module
from prodimopy import plot_models as plot_disk_models_module
from prodimopy import plot_mc as plot_mc_module
from prodimopy import plot_slab as plot_slab_module
from prodimopy.observables import plot_casasim as plot_casasim_module

from prodimopy_mcp.server import mcp  # import the shared instance
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

_READ_MODULES = {
    "read_disk": read_disk_module,
    "read_mc": read_mc_module,
    "read_slab": read_slab_module,
    "read_casasim": read_casasim_module,
}

_PLOT_MODULES = {
    "plot_disk": plot_disk_module,
    "plot_disk_models": plot_disk_models_module,
    "plot_mc": plot_mc_module,
    "plot_slab": plot_slab_module,
    "plot_casasim": plot_casasim_module,  
}


# Synonym -> module alias, used to auto-restrict the search when the caller
# doesn't pass an explicit `module` but the keyword clearly implies one.
# Checked in this order; first match wins.
_PLOT_MODULE_SYNONYMS = [
    ("plot_disk", ["disk", "protoplanetary disk", "protoplanetary disk model", "prodimo model","plot disk"]),
    ("plot_slab", ["slab"]),
    ("plot_mc", ["molecular cloud", "0d chemistry", "0d model", " mc "]),
    ("plot_casasim", ["CASA simulation", "ALMA simulation","ALMA observables"]),
    ("plot_disk_models", ["compare", "comparison", "multiple model", "several models", "model grid"]),
]

_READ_MODULE_SYNONYMS = [
    ("read_disk", ["disk", "protoplanetary disk", "protoplanetary disk model", "prodimo model","read disk"]),
    ("read_slab", ["slab","slab model"]),
    ("read_mc", ["molecular cloud", "0d chemistry", "0d model", " mc "]),
    ("read_casasim", ["CASA simulation", "ALMA simulation","ALMA observables"]),
]



def _infer_module(keyword: str, synonymsmap: dict) -> str | None:
    kw = f" {keyword.lower()} "
    for module_alias, synonyms in synonymsmap:
        if any(syn in kw for syn in synonyms):
            return module_alias
    return None


def _list_functions(modules:dict , synonymsmap: dict, keyword: str | None = None, module: str | None = None,) -> list[dict]:
    """
    Helper function that lists functions/classes in the given modules, optionally filtered by keyword and/or module.

    Parameters:
        modules: A dictionary mapping module names to module objects.
        synonymsmap: A dictionary mapping module aliases to lists of synonyms.
        keyword: An optional keyword to filter functions/classes by name or docstring.
        module: An optional module name to restrict the search to a specific module.

    Returns:
        A list of dictionaries, each containing information about a function/class:
            - 'module': The module name.
            - 'class': The class name (if applicable).
            - 'name': The function/method name.
            - 'signature': The function/method signature.
            - 'doc': The first paragraph of the docstring.

    """

    if module is not None and module not in modules:
        raise ValueError(
            f"Unknown module '{module}'. Must be one of: {', '.join(modules)}"
        )

    inferred = None
    if module is None and keyword:
        inferred = _infer_module(keyword,synonymsmap)

    active_alias = module or inferred
    modules_to_search = (
        {active_alias: modules[active_alias]} if active_alias else modules
    )

    # if we inferred the module from the keyword (e.g. "slab" -> plot_slab),
    # don't also apply that same keyword as a text filter within the module,
    # since it already did its job selecting the module and might otherwise
    # wrongly exclude functions whose docstrings don't repeat the word.
    text_filter = keyword if (keyword and not inferred) else None

    results = []
    for mod_name, mod in modules_to_search.items():
        for name, obj in inspect.getmembers(mod):
            if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                continue
            if name.startswith("_"):
                continue
            if getattr(obj, "__module__", None) != mod.__name__:
                continue

            if inspect.isclass(obj):
                # Emit methods of the class instead of the class itself,
                # so callers see the actual plot_*/read_* methods.
                for meth_name, meth in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if meth_name.startswith("_"):
                        continue
                    doc = inspect.getdoc(meth) or ""
                    if text_filter and text_filter.lower() not in (meth_name + doc).lower():
                        continue
                    try:
                        sig = str(inspect.signature(meth))
                    except (ValueError, TypeError):
                        sig = "(...)"
                    results.append({
                        "module": mod_name,
                        "class": name,
                        "name": meth_name,
                        "signature": sig,
                        "doc": doc.split("\n\n")[0],
                    })
            else:
                doc = inspect.getdoc(obj) or ""
                if text_filter and text_filter.lower() not in (name + doc).lower():
                    continue
                results.append({
                    "module": mod_name,
                    "name": name,
                    "signature": str(inspect.signature(obj)),
                    "doc": doc.split("\n\n")[0],
                })
    return results


@mcp.tool(annotations=READ_ONLY)
def list_read_functions(keyword: str | None = None,module: str | None = None) -> list[dict]:
    """
    List prodimopy functions/classes for reading ProDiMo model output.

    prodimopy spreads reading across four modules:
    - read_disk: reading standard disk model output (or just read)
    - read_mc: reading molecular cloud model output (0D chemistry models)
    - read_slab: reading slab model output
    - read_casasim: reading synthetic observations/observables from CASA simulations

    Optionally filter by a keyword matching name or docstring (e.g. 'sed', 'line'),
    and/or restrict to one module explicitly (one of: read_disk, read_mc, read_slab, read_casasim).
    If module is not given but the keyword clearly refers to one of the specialised
    modules (e.g. 'slab', 'Molecular Cloud', 'compare models'), the search is automatically
    restricted to that module.
    """

    results = _list_functions(_READ_MODULES, _READ_MODULE_SYNONYMS, keyword, module)
    return results


@mcp.tool(annotations=READ_ONLY)
def list_plot_functions(keyword: str | None = None, module: str | None = None) -> list[dict]:
    """
    List prodimopy functions/classes for plotting ProDiMo model output.

    prodimopy spreads plotting across four modules:
    - plot_disk: general/standard single-model disk plots (SEDs, line profiles, structure, etc.)
    - plot_disk_models: comparing/plotting multiple disk models together
    - plot_mc: plots for molecular cloud models (0D chemistry models)
    - plot_slab: plots specific to slab model output
    - plot_casasim: plots for synthetic observations/observables from CASA simulations

    Optionally filter by a keyword matching name or docstring (e.g. 'sed', 'line'),
    and/or restrict to one module explicitly (one of: plot_disk, plot_disk_models, plot_mc, plot_slab, plot_casasim).
    If module is not given but the keyword clearly refers to one of the specialised
    modules (e.g. 'slab', 'Molecular Cloud', 'compare models'), the search is automatically
    restricted to that module.
    """
    
    results = _list_functions(_PLOT_MODULES, _PLOT_MODULE_SYNONYMS, keyword, module)
    return results


_ALL_MODULES = {**_READ_MODULES, **_PLOT_MODULES}


@mcp.tool(annotations=READ_ONLY)
def describe_function(name: str, module: str | None = None, class_name: str | None = None) -> dict | None:
    """
    Return the full docstring and signature for a named prodimopy function or method.

    Use this after list_plot_functions or list_read_functions to get the complete
    parameter documentation for a specific function.

    Parameters
    ----------
    name : str
        The exact function or method name to look up (e.g. ``'plot_lineprofile'``,
        ``'read_prodimo'``).

    module : str, optional
        Restrict the search to a specific module (e.g. ``'plot_disk'``,
        ``'read_disk'``). If omitted all modules are searched.

    class_name : str, optional
        Restrict the search to methods of a specific class (e.g. ``'Plot'``,
        ``'PlotModels'``). If omitted all classes are searched.

    Returns
    -------
    dict or None
        A dict with keys ``module``, ``class`` (if a method), ``name``,
        ``signature``, and ``doc`` (full docstring), or ``None`` if not found.
    """
    modules_to_search = (
        {module: _ALL_MODULES[module]}
        if module and module in _ALL_MODULES
        else _ALL_MODULES
    )

    for mod_name, mod in modules_to_search.items():
        for obj_name, obj in inspect.getmembers(mod):
            if obj_name.startswith("_"):
                continue
            if getattr(obj, "__module__", None) != mod.__name__:
                continue

            if inspect.isclass(obj):
                if class_name and obj_name != class_name:
                    continue
                for meth_name, meth in inspect.getmembers(obj, predicate=inspect.isfunction):
                    if meth_name != name:
                        continue
                    try:
                        sig = str(inspect.signature(meth))
                    except (ValueError, TypeError):
                        sig = "(...)"
                    return {
                        "module": mod_name,
                        "class": obj_name,
                        "name": meth_name,
                        "signature": sig,
                        "doc": inspect.getdoc(meth) or "",
                    }
            elif inspect.isfunction(obj):
                if obj_name != name:
                    continue
                return {
                    "module": mod_name,
                    "name": obj_name,
                    "signature": str(inspect.signature(obj)),
                    "doc": inspect.getdoc(obj) or "",
                }
    return None


def _prodimopy_root() -> Path:
    """Return the root directory of the installed prodimopy package."""
    import prodimopy
    return Path(inspect.getfile(prodimopy)).parent


@mcp.tool(annotations=READ_ONLY)
def search_source(
    pattern: str,
    filename_glob: str = "*.py",
    max_results: int = 30,
    context_lines: int = 2,
) -> list[dict]:
    """Search the prodimopy source code for a regex pattern.

    Works with any install (editable or regular pip install) by locating
    the package root via ``inspect``.

    Args:
        pattern: A regular expression (case-insensitive) to search for.
            E.g. ``'DataLine'``, ``'def plot_sed'``, ``'species'``.
        filename_glob: Glob pattern to restrict which files are searched.
            Defaults to ``'*.py'`` (all Python source files).
            Examples: ``'read*.py'``, ``'plot*.py'``.
        max_results: Maximum number of matching lines to return (default 30).
        context_lines: Number of lines of context to include before and after
            each match (default 2).
    """
    root = _prodimopy_root()
    regex = re.compile(pattern, re.IGNORECASE)
    matches = []
    for path in sorted(root.rglob(filename_glob)):
        if "__pycache__" in path.parts:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if regex.search(line):
                start = max(0, lineno - 1 - context_lines)
                end = min(len(lines), lineno + context_lines)
                matches.append({
                    "file": str(path.relative_to(root.parent)),
                    "line": lineno,
                    "match": line.rstrip(),
                    "context": lines[start:end],
                })
                if len(matches) >= max_results:
                    return matches
    return matches
