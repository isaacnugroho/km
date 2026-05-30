# Knowledge Management MCP

A neuro-symbolic knowledge management system for AI agents — dual-ontology design with SHACL validation, semantic merge requests, and Git-aligned case graphs.

See [docs/knowledge-management-specification.md](docs/knowledge-management-specification.md) for the full engineering spec.

## Phase 1 status

Phase 1 delivered a runnable MCP server with logging, tests, and stub gates.

## Phase 2 status

Phase 2 adds the case knowledge loop:

- `ingest_case_facts` — parse JSON-LD/Turtle into the active branch graph
- `query_semantic_graph` — read-only SELECT/ASK over case + LO canonical graphs
- `km://case/active-graph` — Turtle serialization of the active branch graph
- Case export pipeline with `on_write` policy (exports to `case-exports/graphs/`)

Still stubbed: SHACL validation, exceptions, semantic MR, git watcher, `km export-case` CLI.

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

Print system status:

```bash
km status
```

Start the MCP server (stdio transport):

```bash
km mcp
```

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

Use the absolute path to your workspace as `cwd` so `.km/config.json` is found.

## Bundled learning ontology

The repo includes a sample LO at [usages/ontologies/hexagonal-architecture/](usages/ontologies/hexagonal-architecture/). `km init` binds it by default.

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `KM_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `KM_LOG_FILE` | — | Optional log file path |
| `KM_WORKSPACE_ROOT` | — | Override workspace root discovery |

All logs go to **stderr** (safe for MCP stdio).

## Tests

```bash
pytest
```

## MCP tools (Phase 1)

| Tool | Phase 1 |
|------|---------|
| `get_system_status` | Implemented |
| `ingest_case_facts` | Implemented |
| `validate_constraints` | Stub |
| `propose_local_exception` | Stub |
| `approve_local_exception` | Stub |
| `query_semantic_graph` | Implemented |
| `propose_semantic_mr` | Stub |
| `approve_semantic_mr` | Stub |

Resource `km://case/active-graph` is also implemented (Phase 2).

## CLI commands

| Command | Description |
|---------|-------------|
| `km init [--path DIR]` | Create `.km/config.json` and case-exports dirs |
| `km status` | Print system status JSON |
| `km mcp` | Start MCP stdio server |
| `km export-case` | Stub (Phase 5) |
