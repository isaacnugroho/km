# Knowledge Management MCP

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

## Phase 1 status

Phase 1 delivered a runnable MCP server with logging, tests, and feature gates.

## Phase 2 status

Phase 2 adds the case knowledge loop:

- `ingest_case_facts` — parse JSON-LD/Turtle into the active branch graph
- `query_semantic_graph` — read-only SELECT/ASK over case + LO canonical graphs
- `km://case/active-graph` — Turtle serialization of the active branch graph
- Case export pipeline with `on_write` policy (exports to `case-exports/graphs/`)

## Phase 3 status

Phase 3 adds constraint enforcement and exception workflow:

- `validate_constraints` — SHACL validation against LO canonical shapes (incremental cache)
- `propose_local_exception` / `approve_local_exception` — human-in-the-loop bypass
- `km://schemas/learning-ontologies` — JSON-LD schema bundle for bound LOs
- `km://case/active-exceptions` — pending and approved exceptions on active branch
- Real `pending_exceptions_count` in `status`

## Phase 4 status

Phase 4 adds semantic merge request governance:

- `propose_semantic_mr` / `approve_semantic_mr` — curator-mode LO promotion (requires `mode: "curator"` on binding)
- `km://learning-ontologies/{id}/canonical` — canonical graph from workspace cache
- `km://learning-ontologies/{id}/governance` — MR records from source LO store
- `km://mr/{ontology-id}/{mr-id}` — derived review markdown (`.km/mrs/`)
- Real `pending_mrs_count` in `status`; LO cache + SHACL refresh on MR approve

## Phase 5 status

Phase 5 adds Git-aligned case lifecycle:

- Git ref watcher (MCP daemon) — branch switch detection, context swap, inheritance
- Branch inheritance — clone-on-write from parent when a new branch graph is empty
- Merge resolver — `auto_merge`, `auto_merge_exception` (default), `no_auto_merge` policies
- `sync_pending_branch_merges` / `resolve_branch_merge` MCP tools — idempotent §5.3 sync while `km mcp` runs
- Persisted processed merge events (`.km/processed-merge-events.json`)
- `km status` / MCP `status` — includes full `pending_branch_merges` payloads
- `km export-case` / MCP `export_case` — export active branch graph + manifest

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

## Bundled learning ontology

The repo includes a sample LO at [usages/ontologies/hexagonal-architecture/](usages/ontologies/hexagonal-architecture/). `km init` binds it by default.

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

| Command                | Description                                                              |
| :--------------------- | :----------------------------------------------------------------------- |
| `km init [--path DIR]` | Create `.km/config.json` and case-exports dirs                           |
| `km status`            | Print system status JSON                                                 |
| `km mcp`               | Start MCP stdio server (enables git watcher)                             |
| `km export-case`       | Export active branch graph to `case-exports/` (or use MCP `export_case`) |
