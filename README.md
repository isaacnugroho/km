# Knowledge Management MCP

[![GitHub Sponsors](https://img.shields.io/github/sponsors/isaacnugroho?label=Sponsor&logo=github)](https://github.com/sponsors/isaacnugroho)
[![CI](https://github.com/isaacnugroho/km/actions/workflows/ci.yml/badge.svg)](https://github.com/isaacnugroho/km/actions/workflows/ci.yml)

A neuro-symbolic knowledge management system for AI agents — dual-ontology design with SHACL validation, semantic merge requests, and Git-aligned case graphs.

See [docs/knowledge-management-specification.md](docs/knowledge-management-specification.md) for the full engineering spec.

## Roadmap status

| Phase | Focus                                                | Status   |
| :---- | :--------------------------------------------------- | :------- |
| 1     | Bootstrap, LO cache, `status`, MCP/CLI surface       | Complete |
| 2     | Case ingest, SPARQL query, case export pipeline      | Complete |
| 3     | SHACL validation, local exceptions, schema resources | Complete |
| 4     | Semantic merge requests, LO governance resources     | Complete |
| 5     | Git branch sync, merge policies, `export-case` CLI   | Complete |

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync --extra dev
```

## Quick start

Initialize a workspace in your project root (creates `.km/config.json` and `case-exports/`):

```bash
km init
```

Bind a Learning Ontology from the [external ontologies repository](https://github.com/isaacnugroho/ontologies):

```bash
git clone https://github.com/isaacnugroho/ontologies.git
km init --lo-source ../ontologies/<package-dir>
```

See [usages/ontologies/README.md](usages/ontologies/README.md) for LO package layout and binding details.

Print system status:

```bash
km status
```

Start the MCP server (stdio transport):

```bash
km mcp
```

The MCP server does **not** create or open `.km` files on startup. Agents call the MCP **`setup`** tool with `workspace_directory` before any other KM tool (see [usages/agents.md](usages/agents.md)).

## Cursor MCP configuration

Add to your Cursor MCP settings (`.cursor/mcp.json` or Cursor Settings → MCP):

```json
{
  "mcpServers": {
    "km": {
      "command": "km",
      "args": ["mcp"],
      "cwd": "/path/to/your/workspace"
    }
  }
}
```

Use the absolute path to your workspace as `cwd` so agents can pass the same path to **`setup`**. Other MCP tools require **`setup`** first even when `cwd` is set.

## Antigravity / global MCP configuration

When the IDE cannot set per-workspace MCP `cwd` (e.g. Antigravity), configure `km mcp` globally without `cwd`:

```json
{
  "mcpServers": {
    "km": {
      "command": "km",
      "args": ["mcp"]
    }
  }
}
```

Agents must call MCP **`setup`** with the project root `workspace_directory` at the start of each session before using other KM tools.

### Standalone binary (PyInstaller)

If `km` is not on the IDE's `PATH` (common on Linux when the binary lives in `~/.local/bin` or `dist/`), use the **absolute path** to the executable:

```json
{
  "mcpServers": {
    "km": {
      "command": "/absolute/path/to/km",
      "args": ["mcp"],
      "cwd": "/path/to/your/workspace"
    }
  }
}
```

Example after `./scripts/build-linux.sh`:

```json
"command": "/werkz/personal/km/dist/km"
```

`spawn km ENOENT` means the MCP client could not resolve `command` — fix by using a full path or installing `km` somewhere the GUI inherits on `PATH` (e.g. `/usr/local/bin`).

VS Code uses the same shape under `.vscode/mcp.json`, but the root key is `"servers"` instead of `"mcpServers"`.

## Learning ontologies

Learning Ontology packages live in the separate [ontologies](https://github.com/isaacnugroho/ontologies) repository. `km init` creates an empty `learning_ontologies` list; use `--lo-source` to bind a package at init time, or edit `.km/config.json` afterward.

Package layout and binding instructions: [usages/ontologies/README.md](usages/ontologies/README.md).

## Logging

| Variable            | Default | Description                         |
| :------------------ | :------ | :---------------------------------- |
| `KM_LOG_LEVEL`      | `INFO`  | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KM_LOG_FILE`       | —       | Optional log file path              |
| `KM_WORKSPACE_ROOT` | —       | Override workspace root discovery   |

All logs go to **stderr** (safe for MCP stdio).

## Tests

```bash
pytest
```

Coverage runs by default (terminal summary, `htmlcov/index.html`, and `coverage.xml`). CI enforces at least **80% per `src/km` module**:

```bash
python scripts/check_coverage_per_file.py --min 80
```

To skip coverage during local test runs:

```bash
pytest --no-cov
```

## MCP tools

| Tool                         | Status                                    |
| :--------------------------- | :---------------------------------------- |
| `status`                     | Implemented (same payload as `km status`) |
| `export_case`                | Implemented (same as `km export-case`)    |
| `ingest_case_facts`          | Implemented                               |
| `query_semantic_graph`       | Implemented                               |
| `validate_constraints`       | Implemented                               |
| `propose_local_exception`    | Implemented                               |
| `approve_local_exception`    | Implemented                               |
| `propose_semantic_mr`        | Implemented (curator binding)             |
| `approve_semantic_mr`        | Implemented (curator binding)             |
| `sync_pending_branch_merges` | Implemented                               |
| `resolve_branch_merge`       | Implemented                               |

Resources: eight MCP resources are implemented (`km://schemas/learning-ontologies`, `km://case/active-graph`, `km://case/active-exceptions`, `km://case/pending-merges`, `km://learning-ontologies/{id}/canonical`, `km://learning-ontologies/{id}/governance`, `km://mr/{ontology-id}/{mr-id}`).

## CLI commands

| Command                    | Description                                                              |
| :------------------------- | :----------------------------------------------------------------------- |
| `km --version`             | Print package version                                                    |
| `km init [--path DIR]`     | Create `.km/config.json` and case-exports dirs                           |
| `km init --lo-source PATH` | Initialize and bind one Learning Ontology package                        |
| `km status`                | Print system status JSON                                                 |
| `km mcp`                   | Start MCP stdio server (enables git watcher)                             |
| `km export-case`           | Export active branch graph to `case-exports/` (or use MCP `export_case`) |

## Support

If this project helps your work, consider [sponsoring on GitHub](https://github.com/sponsors/isaacnugroho).
