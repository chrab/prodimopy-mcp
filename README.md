# prodimopy-mcp

An [MCP](https://modelcontextprotocol.io) server for [prodimopy](https://gitlab.astro.rug.nl/prodimo/prodimopy), the Python package for the [ProDiMo](https://prodimo.iwf.oeaw.ac.at/) code. With this server, an AI agent can look up prodimopy functions, the prodimopy documentation and the example notebooks.

This is still experimental, but it should be safe to use. The server runs locally on your machine.

The server provides these tools:

| Tool | Purpose |
|------|---------|
| `list_read_functions`, `list_plot_functions` | List the read and plot functions of prodimopy |
| `describe_function` | Signature and docstring of a prodimopy function or method |
| `search_source` | Search the source code of the installed prodimopy |
| `search_docs` | Search the prodimopy documentation |
| `list_notebooks`, `search_notebooks`, `open_notebook` | Find example notebooks and copy one to a directory |
| `ping` | Check that the server runs |

The introspection tools use the prodimopy version that is installed together with prodimopy-mcp. The documentation and notebooks come from the prodimopy release given by `prodimopy-ref` in `pyproject.toml`.

## Installation

```console
pip install prodimopy-mcp
```

This also installs prodimopy. You then have the command `prodimopy-mcp`. To test it, run:

```console
prodimopy-mcp
```

If there is no error message, the server works. Stop it with Ctrl+C.

> This package replaces `pip install prodimopy[agent]`. The command name `prodimopy-mcp` is the same, so existing MCP client configurations keep working.

## Use with an AI client

How you add the server depends on your AI client. What you need is that the client can start `prodimopy-mcp` and talk to it over stdio.

In VS Code, add the server to `.vscode/mcp.json` in your project (see [MCP servers in VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers)). For a conda environment called `prodimopy`:

```json
{
  "servers": {
    "prodimopy-mcp-server": {
      "type": "stdio",
      "command": "conda",
      "args": ["run", "--no-capture-output", "-n", "prodimopy", "prodimopy-mcp"]
    }
  }
}
```

If you use the pixi environment of this repository, use `"command": "pixi"` and `"args": ["run", "--manifest-path", "/path/to/prodimopy-mcp", "prodimopy-mcp"]`.

Then ask your agent something like "What plotting functionality does prodimopy provide?".

## Development

The development environments are managed with [pixi](https://pixi.sh) (see `pyproject.toml`):

```console
pixi run sync-data      # generate the documentation and notebook data (see below)
pixi run test           # run the tests
pixi shell              # shell in the default environment
```

### Documentation and notebook data

The server ships text versions of the prodimopy documentation and the example notebooks (without outputs) in `src/prodimopy_mcp/data/`. This data is **generated, not tracked by git**, but it is included in the sdist and the wheel.

`scripts/sync_data.py` clones prodimopy at the git ref in `pyproject.toml`:

```toml
[tool.prodimopy-mcp]
prodimopy-ref = "v2.8.0"
```

Then it builds the prodimopy documentation with Sphinx, converts the pages to text and copies the notebooks. There are two sources:

| Task | Source |
|------|--------|
| `pixi run sync-data` | local prodimopy repository: `$PRODIMOPY_SRC`, default `../prodimopy` |
| `pixi run sync-data-gitlab` | https://gitlab.astro.rug.nl/prodimo/prodimopy.git |

Both give the same result. The local variant clones the committed state of the ref from your repository; it does not change your working tree or branch, and uncommitted changes are not included. If the tag is missing locally, run `git fetch --tags` in the prodimopy repository.

For development you can use another branch or tag: `pixi run sync-data --ref master`.

After a new prodimopy release:

1. Set `prodimopy-ref` to the new tag.
2. Run `pixi update prodimopy`, so that the installed prodimopy matches the tag (`sync-data` warns if it does not).
3. Release a new prodimopy-mcp version.

### Release

```console
pixi run release-build      # check clean tree, sync data, tests, build, twine check, data check
pixi run upload-testpypi    # upload dist/* to TestPyPI
pixi run upload-pypi        # upload dist/* to PyPI
```

The version comes from the git tags (setuptools-scm). `release-build` stops if the working tree has uncommitted changes. `scripts/check_dist.py` makes sure that the sdist and the wheel contain the generated data. The upload tasks ask for the API token (input is hidden).

## License

MIT, see [LICENSE](LICENSE).
