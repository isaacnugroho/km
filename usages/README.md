# KM MCP Usage Walkthrough

This guide walks through a complete **agent + developer** session using the Knowledge Management MCP tools end to end. For operational detail, see [agents.md](agents.md) (lifecycle and patterns) and [skills.md](skills.md) (reusable recipes).

---

## What you need

A workspace with KM initialized:

```
my-app/
├── .git/
├── case-exports/            # Case Git authority (commit with source)
│   ├── graphs/
│   ├── governance/
│   └── sync-manifest.json
├── .km/                     # runtime (Git ignored)
│   ├── config.json
│   ├── case_quads.db
│   ├── lo-cache/
│   └── mrs/                 # derived MR review docs (created on demand)
└── src/
```

Example `.km/config.json`:

```json
{
  "workspace_id": "my-app-dev",
  "learning_ontologies": [
    {
      "ontology_id": "react-conventions",
      "source": "../km-org-ontologies/react-conventions",
      "mode": "read_only"
    }
  ],
  "quad_store": {
    "engine": "sqlite-quad",
    "storage_path": "./.km/case_quads.db"
  },
  "lo_cache": { "base_path": "./.km/lo-cache" },
  "case_exports": { "base_path": "./case-exports", "export_policy": "on_commit" },
  "branch_merge": { "policy": "auto_merge_exception" }
}
```

`case_exports.export_policy` controls when Case Turtle files are written (default `on_commit` — see spec §2.6). Commit `case-exports/` with application changes for audit and review.

`branch_merge.policy` controls Case graph sync after Git merge (see spec §5.3): `auto_merge_exception` (default) auto-imports approved exceptions then prompts for remaining facts; `auto_merge` imports everything; `no_auto_merge` prompts for the entire source graph (DELETE there also discards exceptions).

Bundled LO packages ship with this repo under [ontologies/](ontologies/README.md) (e.g. `hexagonal-architecture`).

The KM MCP server must be running and connected to your agent (Cursor, CLI, or other MCP client).

---

## Scenario

You add a React hook `useCanvasDrag.ts` that emits high-frequency pointer events. The agent must:

1. Align with loaded Learning Ontology schemas
2. Register what was built in the Case Ontology
3. Validate against SHACL shapes
4. Handle a violation (fix, or propose an exception)
5. Optionally promote a reusable pattern to a Learning Ontology (curator workspace only)

---

## Walkthrough

### Step 0 — Orient the session

**Tool:** `get_system_status`  
**Resource:** `km://schemas/learning-ontologies`

```text
get_system_status()
→ {
    "active_branch": "feature/collaborative-canvas",
    "learning_ontologies": [
      {
        "ontology_id": "react-conventions",
        "source": "/abs/path/km-org-ontologies/react-conventions",
        "mode": "read_only",
        "cache_path": ".km/lo-cache/react-conventions",
        "cache_synced_at": "2026-05-30T08:00:00Z"
      }
    ],
    "pending_exceptions_count": 0,
    "pending_mrs_count": 0,
    "branch_merge_policy": "auto_merge_exception",
    "pending_branch_merges_count": 0
  }
```

Read `km://schemas/learning-ontologies` to learn allowed classes (e.g. `react:HighFrequencyEventHook`) and governed properties (e.g. `react:throttleRateMs`).

Optionally inspect existing branch facts:

```text
Resource: km://case/active-graph
```

Or run a targeted query:

```text
query_semantic_graph({
  "query": "PREFIX local: <http://app.local/hooks#> SELECT ?hook WHERE { ?hook a <http://ontologies.react.org/core#HighFrequencyEventHook> }"
})
```

---

### Step 1 — Ingest case facts

After implementing or modifying code, extract **structural** facts (not raw source files) and write them to the active branch graph.

**Tool:** `ingest_case_facts`

```turtle
@prefix react: <http://ontologies.react.org/core#> .
@prefix local: <http://app.local/hooks#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

local:useCanvasDrag a react:HighFrequencyEventHook ;
    react:throttleRateMs 32 ;
    react:filePath "src/hooks/useCanvasDrag.ts"^^xsd:string .
```

```text
ingest_case_facts({
  "facts": "<turtle above>",
  "format": "turtle"
})
→ { "status": "success", "triples_added": 3 }
```

Confirm `triples_added > 0`. Facts land in the named graph for the active Git branch (e.g. `http://km.local/graphs/feature/collaborative-canvas`).

---

### Step 2 — Validate constraints

**Tool:** `validate_constraints`

```text
validate_constraints()
→ { "conforms": true, "violations": [] }
```

If `conforms` is `false`, inspect each violation:

| Field          | Meaning                         |
| :------------- | :------------------------------ |
| `focus_node`   | Case element that failed        |
| `source_shape` | SHACL shape URI                 |
| `message`      | Human-readable rule explanation |

**Branch A — Fix the code:** Adjust implementation, re-ingest facts, call `validate_constraints` again.

**Branch B — Request an exception:** Continue to Step 3.

---

### Step 3 — Propose a local exception (when refactoring is not acceptable)

Suppose validation fails because `react:throttleRateMs` is below the shape minimum, but zero throttle is required for rendering quality.

**Tool:** `propose_local_exception`

```text
propose_local_exception({
  "bypasses_shape": "http://ontologies.react.org/core#HighFrequencyThrottleShape",
  "target_node": "http://app.local/hooks#useCanvasDrag",
  "rationale": "Canvas drag requires unthrottled coordinates for sub-frame visual fidelity."
})
→ {
    "exception_id": "http://km.local/exceptions/uuid-88aef402-990a",
    "status": "PENDING_APPROVAL"
  }
```

Prompt the developer:

```text
approve km://case/active-exceptions/uuid-88aef402-990a
```

When the developer runs that command, the agent calls:

**Tool:** `approve_local_exception`

```text
approve_local_exception({
  "exception_id": "http://km.local/exceptions/uuid-88aef402-990a",
  "approver": "DeveloperJane",
  "signature": "sig_…"
})
→ { "status": "APPROVED", "timestamp": "2026-05-30T10:15:00Z" }
```

Re-run `validate_constraints()` — it should pass with the approved exception recorded in the branch graph.

**Resource:** `km://case/active-exceptions` lists pending and approved exceptions for the workspace.

---

### Step 4 — Promote knowledge to a Learning Ontology (curator only)

When a local pattern should become global policy, submit a semantic Merge Request. The target binding must have `"mode": "curator"`.

**Tool:** `propose_semantic_mr`

`target_ontology` accepts either the LO `base_uri` or `ontology_id`.

```text
propose_semantic_mr({
  "target_ontology": "react-conventions",
  "rationale": "High-frequency hooks must be throttled to prevent WebSocket saturation.",
  "diff_insertions": "@prefix react: <http://ontologies.react.org/core#> .\n@prefix sh: <http://www.w3.org/ns/shacl#> .\n\nreact:HighFrequencyThrottleShape a sh:NodeShape ;\n    sh:targetClass react:HighFrequencyEventHook ;\n    sh:property [\n        sh:path react:throttleRateMs ;\n        sh:minInclusive 16 ;\n        sh:maxInclusive 200\n    ] .",
  "diff_deletions": ""
})
→ { "mr_id": "MR-042", "status": "PENDING_APPROVAL" }
```

The server:

- Writes proposal + governance triples to the **source** LO package
- Upserts `{source}/exports/governance/MR-042.ttl`
- Does **not** update the workspace cache yet
- Creates a review doc at `.km/mrs/mr-react-conventions-042.md`

Prompt the developer:

```text
approve .km/mrs/mr-react-conventions-042.md
```

**Tool:** `approve_semantic_mr`

```text
approve_semantic_mr({
  "doc_identifier": ".km/mrs/mr-react-conventions-042.md"
})
→ {
    "status": "APPROVED",
    "mr_id": "MR-042",
    "target_ontology": "http://ontologies.react.org/core",
    "timestamp": "2026-05-30T11:00:00Z"
  }
```

On approval the server merges into the source canonical graph, regenerates `exports/main.ttl`, updates `exports/governance/{mr-id}.ttl`, and **fully rebuilds** `.km/lo-cache/`.

**Tool:** `get_system_status` — confirm cache sync and updated bindings.

**Resources for review:**

- `km://learning-ontologies/react-conventions/governance` — MR records (source store)
- `km://mr/react-conventions/MR-042` — derived review document

---

## Tool reference (quick)

| Order | Tool                               | When to use                                                              |
| :---- | :--------------------------------- | :----------------------------------------------------------------------- |
| 1     | `get_system_status`                | Session start; after MR approval                                         |
| —     | `km://schemas/learning-ontologies` | Before ingesting facts                                                   |
| 2     | `ingest_case_facts`                | After code/design changes; commit `case-exports/` when using `on_commit` |
| 3     | `query_semantic_graph`             | Inspect case + LO canonical state                                        |
| 4     | `validate_constraints`             | Before finishing a task                                                  |
| 5     | `propose_local_exception`          | Legitimate shape bypass needed                                           |
| 6     | `approve_local_exception`          | After developer approves exception                                       |
| 7     | `propose_semantic_mr`              | Promote pattern to LO (curator)                                          |
| 8     | `approve_semantic_mr`              | After developer approves MR                                              |

| Resource                                   | Purpose                                                               |
| :----------------------------------------- | :-------------------------------------------------------------------- |
| `km://schemas/learning-ontologies`         | LO classes, properties, shapes (cache canonical)                      |
| `km://case/active-graph`                   | Current branch case facts (runtime); Git diff: `case-exports/graphs/` |
| `km://case/active-exceptions`              | Pending and approved exceptions                                       |
| `km://learning-ontologies/{id}/canonical`  | One LO canonical export                                               |
| `km://learning-ontologies/{id}/governance` | MR governance (source store)                                          |
| `km://mr/{ontology-id}/{mr-id}`            | Derived MR review document                                            |

---

## Typical agent loop

```mermaid
graph TD
    Start([Task start]) --> Status[get_system_status + schemas]
    Status --> Code[Modify code]
    Code --> Ingest[ingest_case_facts]
    Ingest --> Validate[validate_constraints]
    Validate -->|conforms| Done([Complete task])
    Validate -->|violations| Fix{Fixable?}
    Fix -->|yes| Code
    Fix -->|no| Exception[propose_local_exception → human approve → approve_local_exception]
    Exception --> Validate
    Validate -->|pattern is global| MR[propose_semantic_mr → human approve → approve_semantic_mr]
    MR --> Status
```

---

## Further reading

| Document                                                                                       | Contents                                                          |
| :--------------------------------------------------------------------------------------------- | :---------------------------------------------------------------- |
| [agents.md](agents.md)                                                                         | Agent lifecycle, tool patterns, MR lifecycle                      |
| [skills.md](skills.md)                                                                         | Step-by-step skills: ingestion, linting, exceptions, MR promotion |
| [../docs/brief.md](../docs/brief.md)                                                           | System overview and MCP interface summary                         |
| [../docs/knowledge-management-specification.md](../docs/knowledge-management-specification.md) | Full engineering specification                                    |
| [../docs/simulations/app-feature-simulation.md](../docs/simulations/app-feature-simulation.md) | Multi-ontology feature walkthrough                                |
| [../docs/simulations/cake-recipe-simulation.md](../docs/simulations/cake-recipe-simulation.md) | Single-ontology domain walkthrough                                |
