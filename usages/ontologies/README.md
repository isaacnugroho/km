# Learning Ontology Packages

Self-contained **Learning Ontology (LO) source packages** for use with the Knowledge Management MCP. Each package is a directory the daemon can bind to via `.km/config.json`; structure and semantics follow [knowledge-management-specification.md](../../docs/knowledge-management-specification.md) §2.4–2.5.

An LO package can live anywhere on disk — sibling repo, submodule, path under this repo, or system path. The workspace references it by path; named graph URIs depend on `ontology_id` only, not on where the directory sits.

## External ontology repository

Published LO packages are maintained in a separate repository:

- **Repository:** https://github.com/isaacnugroho/ontologies.git
- **Clone:** `git clone https://github.com/isaacnugroho/ontologies.git`

After cloning, bind a package from your application workspace:

```bash
km init --lo-source ../ontologies/<package-dir>
```

Or add a binding manually in `.km/config.json` (see [Workspace binding](#workspace-binding) below).

---

## LO package directory layout

Every bindable LO directory MUST contain at least:

```
{ontology-id}/
├── README.md              # Domain purpose, vocabulary summary, case-fact examples
├── config.json            # ontology_id, base_uri, prefix, quad_store, named_graphs
└── exports/
    └── main.ttl           # Git-authoritative canonical graph (vocabulary + SHACL)
```

Recommended additions:

```
{ontology-id}/
├── lo_quads.db            # Runtime quad-store (Git ignored; created by MCP)
└── exports/
    └── governance/        # One Turtle file per semantic MR (Git tracked)
        └── {mr-id}.ttl
```

| Path                          | Git         | Purpose                                                                                   |
| :---------------------------- | :---------- | :---------------------------------------------------------------------------------------- |
| `README.md`                   | Tracked     | Human-facing domain docs; agents use `km://schemas/learning-ontologies`, not this file    |
| `config.json`                 | Tracked     | Package identity and named graph URIs; `ontology_id` must match the workspace binding     |
| `exports/main.ttl`            | Tracked     | Approved ontology state — classes, properties, and SHACL shapes agents validate against   |
| `exports/governance/`         | Tracked     | MR lifecycle records (`{mr-id}.ttl` per merge request); may be empty for a new package    |
| `exports/governance/.gitkeep` | Tracked     | Optional; keeps an empty governance directory in Git until the first MR                   |
| `lo_quads.db`                 | **Ignored** | Source-side runtime store for curator MR propose/approve; rebuilt from exports when stale |

Add `lo_quads.db` to the LO repo's `.gitignore`. Git authority is always `exports/main.ttl` and `exports/governance/*.ttl`.

---

## `config.json`

Required fields (example):

```json
{
  "ontology_id": "my-domain",
  "base_uri": "http://example.org/my-domain",
  "prefix": "mdom",
  "quad_store": {
    "engine": "sqlite-quad",
    "storage_path": "./lo_quads.db"
  },
  "named_graphs": {
    "canonical": "http://km.local/learning-ontologies/my-domain/canonical",
    "governance": "http://km.local/learning-ontologies/my-domain/governance"
  }
}
```

| Field                     | Requirement                                                                                        |
| :------------------------ | :------------------------------------------------------------------------------------------------- |
| `ontology_id`             | Stable slug; MUST match `ontology_id` in the workspace binding and SHOULD match the directory name |
| `base_uri`                | Public ontology IRI for domain terms (namespace root; trailing `#` added for Turtle)               |
| `prefix`                  | SPARQL/Turtle prefix for domain terms (e.g. `mdom:`); defaults to `ontology_id` with `-` → `_`     |
| `named_graphs.canonical`  | `http://km.local/learning-ontologies/{ontology_id}/canonical`                                      |
| `named_graphs.governance` | `http://km.local/learning-ontologies/{ontology_id}/governance`                                     |

---

## `exports/main.ttl`

The canonical export is what the MCP imports into `.km/lo-cache/{ontology-id}/` on startup. It should be self-contained for the domain:

- **Ontology declaration** — `owl:Ontology` with label, comment, version
- **Vocabulary** — domain classes and properties (`owl:Class`, `owl:ObjectProperty`, etc.)
- **SHACL shapes** — constraints agents enforce via `validate_constraints`

Pending MR proposal triples do not belong here; they live in proposal named graphs inside `{source}/lo_quads.db` until approved and merged into `main.ttl`.

If `exports/governance/` is missing or empty, cache sync still succeeds (empty governance graph).

---

## Workspace binding

Add one object per LO under `learning_ontologies` in `.km/config.json`. `source` must point at the **package root** — the directory that contains `config.json` and `exports/`.

```json
{
  "workspace_id": "my-app-dev",
  "learning_ontologies": [
    {
      "ontology_id": "my-domain",
      "source": "../ontologies/my-domain",
      "mode": "read_only"
    }
  ],
  "lo_cache": { "base_path": "./.km/lo-cache" }
}
```

### Path resolution

| Form                                   | Resolved against                             |
| :------------------------------------- | :------------------------------------------- |
| Absolute (`/opt/km/ontologies/baking`) | Used as-is                                   |
| Relative (`../ontologies/baking`)      | Workspace root (directory containing `.km/`) |
| Home (`~/km/ontologies/baking`)        | User home directory                          |

### Access modes

| `mode`      | Agent validation / query    | `propose_semantic_mr`              | `approve_semantic_mr`             |
| :---------- | :-------------------------- | :--------------------------------- | :-------------------------------- |
| `read_only` | Yes (cached canonical only) | Rejected                           | Rejected                          |
| `curator`   | Yes (cached canonical only) | Writes to **source** `lo_quads.db` | Merges in source; refreshes cache |

Use `read_only` in application repos that consume an LO. Use `curator` on the LO source repo (or a maintainer workspace) when proposing or approving semantic MRs.

### Startup sync

On MCP startup, for each binding the daemon:

1. Resolves `source` and **fails fast** if the directory or `exports/main.ttl` is missing
2. Compares export checksums against `.km/lo-cache/{ontology-id}/sync-manifest.json`
3. Rebuilds `.km/lo-cache/{ontology-id}/lo_quads.db` from `main.ttl` and `exports/governance/*.ttl` when the manifest, checksums, or cache DB are absent or stale
4. Loads canonical graphs into the in-memory schema cache for `validate_constraints` and `query_semantic_graph`

Agent reads always use the workspace cache canonical graph, never pending MR proposals.

---

## Available ontologies

See the [ontologies repository](https://github.com/isaacnugroho/ontologies) for published packages (for example `hexagonal-architecture`). Each package includes a `README.md` with vocabulary tables, SHACL shape summaries, and case-fact Turtle examples.

---

## Creating a new LO package

1. Create a directory with `config.json`, `exports/main.ttl`, and `README.md` as above
2. Define vocabulary and SHACL in `main.ttl`; add `exports/governance/.gitkeep` if you want the folder tracked before the first MR
3. Add `lo_quads.db` to `.gitignore` in the LO repo
4. Bind it from your workspace `.km/config.json` with matching `ontology_id` and a resolvable `source` path
5. Restart or reconnect the KM MCP — confirm the ontology appears in `status` and `km://schemas/learning-ontologies`

For MR workflow and promotion from Case facts, see [usages/README.md](../README.md) and spec §4–§6.
