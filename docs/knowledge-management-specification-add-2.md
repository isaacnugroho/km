# Knowledge Management System Specification — Addendum 2

**Learning Ontology dependencies, catalog registry, and workspace `rootPath`**

This document is **Addendum 2** to [knowledge-management-specification.md](./knowledge-management-specification.md). It specifies declarative dependency relationships between Learning Ontology (LO) source packages, a catalog registry at the LO repository root, and a workspace configuration key that anchors LO path resolution to that repository.

Addendum 2 is normative where it defines new config keys, catalog format, and validation algorithms. Unchanged behavior in the base specification and [Addendum 1](./knowledge-management-specification-add-1.md) remains authoritative unless explicitly superseded below.

---

## B.0 Motivation and scope

### B.0.1 Problem statement

The base specification (§1.1, §2.4) treats each LO as a **self-contained** package bound independently in `.km/config.json`. Multiple LOs are merged at runtime for SHACL validation and SPARQL query (§2.3), but the platform does **not** declare or enforce relationships between packages.

In practice, domain LOs extend one another. For example, `hexagonal-bloc` subclasses terms from `hexagonal-architecture` and declares `owl:imports` in `exports/main.ttl`, yet the MCP does **not** resolve that import from TTL alone. Operators must manually duplicate parent LOs in workspace config or accept incomplete SHACL coverage.

Without explicit dependency metadata, teams encounter:

| Failure mode                   | Symptom                                                                                                                                                                                  | Current workaround (undesired)                           |
| :----------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------- |
| **Missing prerequisite cache** | Case facts reference `hex:` IRIs but only `hexagonal-bloc` is bound and its dependencies were not loaded; SHACL shapes targeting `hex:` classes never fire or class checks fail silently | Manual duplicate bindings for every parent LO            |
| **Duplicate vocabulary**       | Parallel definitions of the same concept (`SoftwareComponent`, `Module`, `Service`) across LOs with no canonical owner                                                                   | Agents pick inconsistent IRIs; no linter catches overlap |
| **Undocumented composition**   | Extension LO README lists parent bindings; workspace config diverges                                                                                                                     | Tribal knowledge; broken CI when a new LO is added       |
| **Circular extension**         | LO A depends on B, B depends on A (or longer cycles)                                                                                                                                     | Undefined load order; impossible curation                |

### B.0.2 Rationale for ontology dependencies

Learning Ontologies SHOULD form a **directed acyclic graph (DAG)** of extension, not a flat bag of unrelated packages.

**Single definition of a concept.** Generic software structure terms (system, module, service, interface) belong in a **foundation** LO. Pattern-specific LOs (hexagonal architecture, defensive programming, twelve-factor) **extend** foundation classes via `rdfs:subClassOf` and domain properties — they do not redefine parallel class trees for the same real-world entity.

**Predictable validation closure.** SHACL shapes in an extension LO may reference IRIs from a parent LO (`sh:class hex:DrivingPort`). Validation requires parent canonical graphs in the merged shapes dataset. Declared dependencies plus catalog resolution let KM **automatically cache the transitive closure** — operators bind only the LOs they care about; prerequisites load from `{lo-root}` via `catalog.json`.

**Stable curation boundaries.** Semantic MRs remain scoped to one LO package (base §4.1), but dependency edges document which upstream LO versions an extension assumes. Foundation changes propagate predictably; curators see impact before approving breaking MRs.

**Agent schema clarity.** `km://schemas/learning-ontologies` lists all LOs in **effective_cache_set(B)** — explicit bindings plus auto-cached dependencies — with a flag distinguishing **explicit** vs **implicit** entries. Dependency metadata tells agents which prefixes are **foundational** versus **domain-specific**.

**Complement to `owl:imports`.** `owl:imports` in `exports/main.ttl` remains valuable human-facing documentation and semantic Web interoperability. Addendum 2 adds **operational** dependency declarations that KM validates at bootstrap — independent of whether RDF import closure is materialized into `main.ttl`.

### B.0.3 In-scope additions

| ID     | Addition                                                   | Addresses                                                                          |
| :----- | :--------------------------------------------------------- | :--------------------------------------------------------------------------------- |
| **B1** | Optional `dependencies` array in LO `{source}/config.json` | Declarative prerequisite `ontology_id` list per package                            |
| **B2** | `catalog.json` at LO repository root                       | Authoritative registry of available `ontology_id` values and package paths         |
| **B3** | Optional `rootPath` in `.km/config.json`                   | Anchor LO repository root for catalog loading and default `source` resolution      |
| **B4** | Dependency graph validation (including cycle detection)    | Fail fast on circular or unknown dependencies                                      |
| **B5** | Transitive dependency cache resolution                     | Auto-sync `lo-cache/` for all direct and transitive dependencies of every bound LO |
| **B6** | Extended `validate_bindings` report                        | Surface resolved cache set, unresolvable deps, unknown ids, and cycle errors       |

### B.0.4 Out of scope (deferred)

*   Automatic materialization of `owl:imports` closure into `exports/main.ttl` or workspace cache (import/scaffold tooling may use dependency metadata but is not defined here).
*   Cross-package semantic MR workflow (coordinated approve across multiple LO repos).
*   Version pinning (`dependencies: [{ "ontology_id": "…", "min_version": "1.2.0" }]`) — future revision.
*   Duplicate-term linting across LOs (same `rdfs:label`, overlapping intent without `subClassOf` link).
*   Reasoning over `owl:equivalentClass` or OWL DL entailment.

---

## B.1 LO repository catalog (`catalog.json`)

### B.1.1 Purpose

Each LO **repository root** (the directory that directly contains one subdirectory per LO package) MUST provide a machine-readable catalog listing every publishable ontology and its stable `ontology_id`.

The catalog is the **authority for valid dependency targets**. An LO package MUST NOT declare a dependency on an `ontology_id` absent from the catalog at the resolved repository root.

### B.1.2 Location

Given a resolved LO repository root `{lo-root}/`:

```
{lo-root}/
├── catalog.json                 # Registry (this section)
├── hexagonal-architecture/
│   ├── config.json
│   └── exports/main.ttl
├── hexagonal-bloc/
│   ├── config.json
│   └── exports/main.ttl
└── …
```

`catalog.json` MUST live at `{lo-root}/catalog.json` — not inside individual package directories.

### B.1.3 Schema

```json
{
  "catalog_version": "1",
  "ontologies": [
    {
      "ontology_id": "hexagonal-architecture",
      "path": "hexagonal-architecture",
      "label": "Hexagonal Architecture (Ports and Adapters)"
    },
    {
      "ontology_id": "hexagonal-bloc",
      "path": "hexagonal-bloc",
      "label": "Hexagonal BLoC (Flutter Presentation)"
    }
  ]
}
```

| Field                      | Required | Description                                                                                                                                    |
| :------------------------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| `catalog_version`          | Yes      | Schema version string. Implementations MUST accept `"1"`.                                                                                      |
| `ontologies`               | Yes      | Non-empty array of catalog entries (MAY be empty only in a stub repo before first LO is added).                                                |
| `ontologies[].ontology_id` | Yes      | Stable slug; MUST match `{source}/config.json` → `ontology_id` for the package at `path`. MUST be unique within the catalog.                   |
| `ontologies[].path`        | Yes      | Relative path from `{lo-root}/` to the LO package directory. MUST NOT contain `..`. SHOULD equal `ontology_id` when directory name matches id. |
| `ontologies[].label`       | No       | Human-readable title for status reports and documentation generators.                                                                          |

#### Example: foundation + extension registry

```json
{
  "catalog_version": "1",
  "ontologies": [
    {
      "ontology_id": "software-system",
      "path": "software-system",
      "label": "Software System (Foundation)"
    },
    {
      "ontology_id": "hexagonal-architecture",
      "path": "hexagonal-architecture",
      "label": "Hexagonal Architecture"
    },
    {
      "ontology_id": "hexagonal-bloc",
      "path": "hexagonal-bloc",
      "label": "Hexagonal BLoC"
    },
    {
      "ontology_id": "defensive-programming",
      "path": "defensive-programming",
      "label": "Defensive Programming"
    }
  ]
}
```

### B.1.4 Catalog invariants

Implementations MUST enforce:

1. **Unique `ontology_id`** — duplicate ids in `ontologies[]` is a catalog parse error.
2. **Unique `path`** — two entries MUST NOT reference the same filesystem path.
3. **Package presence** — each `path` MUST resolve to a directory containing `{path}/config.json` and `{path}/exports/main.ttl` when the catalog is validated (see §B.5.2).
4. **Id consistency** — catalog `ontology_id` MUST equal `config.json` → `ontology_id` for that package.

---

## B.2 Workspace `rootPath`

### B.2.1 Purpose

`.km/config.json` gains an optional top-level key **`rootPath`**: the filesystem path to the LO repository root (the directory containing `catalog.json` and LO package subdirectories).

When set, `rootPath` enables:

*   Loading and validating `catalog.json`.
*   Resolving LO binding `source` paths relative to the repository root instead of the application workspace root.
*   Validating `dependencies` arrays against the catalog.
*   Resolving and caching the **transitive dependency closure** for every explicitly bound LO (§B.4.4–B.4.5).

When omitted, dependency validation against a catalog is skipped unless a binding `source` path is used to infer a repository root (see §B.2.4).

### B.2.2 Schema addition (workspace config)

Add to `.km/config.json` (alongside existing keys from base §2.2):

```json
{
  "workspace_id": "my-app-dev",
  "rootPath": "../ontologies",
  "learning_ontologies": [
    {
      "ontology_id": "hexagonal-bloc",
      "source": "hexagonal-bloc",
      "mode": "read_only"
    }
  ],
  "lo_cache": { "base_path": "./.km/lo-cache" }
}
```

When `hexagonal-bloc` declares `"dependencies": ["hexagonal-architecture"]` (and that LO declares its own upstream deps), KM **automatically caches** every transitive dependency under `.km/lo-cache/` — explicit workspace bindings are not required for prerequisite LOs (§B.4.5).

| Field      | Required | Description                                                                                                                                                                  |
| :--------- | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rootPath` | No       | Path to LO repository root. Resolved using the same rules as binding `source` (base §2.2 Path Resolution Rules): absolute, relative to **workspace root**, or home-expanded. |

### B.2.3 `source` resolution with `rootPath`

When `rootPath` is present and resolved to `{lo-root}`:

| Binding `source` form           | Resolved package path                                                               |
| :------------------------------ | :---------------------------------------------------------------------------------- |
| **Absolute** path               | Used as-is (ignores `rootPath` for that binding).                                   |
| **Relative** path, not absolute | `{lo-root}/{source}` after normalizing `source` (workspace root is NOT the anchor). |
| **Omitted**                     | `{lo-root}/{ontology_id}/` — allowed only when `rootPath` is set.                   |

When `rootPath` is **absent**, binding `source` resolution is unchanged from base §2.2 (relative to workspace root).

Implementations SHOULD emit a warning (not an error) when `rootPath` is set but a binding uses an absolute `source` outside `{lo-root}`, since catalog validation may not cover that package.

### B.2.4 Inferring `{lo-root}` without `rootPath`

If `rootPath` is omitted but dependency validation is requested (e.g. via `validate_bindings`):

1. For each binding, resolve `source` per base §2.2.
2. Walk parent directories from the package path until a directory containing `catalog.json` is found — that directory is `{lo-root}` for that binding.
3. If bindings imply **multiple distinct** `{lo-root}` values, `validate_bindings` MUST fail with a `multiple_lo_roots` error.

If no `catalog.json` is found, dependency validation is **skipped** with a warning; base binding checks (§2.3) still apply.

---

## B.3 LO package `dependencies`

### B.3.1 Purpose

Each LO source package MAY declare prerequisite ontologies by `ontology_id`. The array documents which other catalog entries MUST be **loaded into the workspace LO cache** (and therefore the merged SHACL / schema / query dataset) whenever this LO is explicitly bound — including all transitive prerequisites (§B.4.5).

### B.3.2 Schema addition (LO package config)

Add to `{source}/config.json` (alongside existing keys from base §2.4):

```json
{
  "ontology_id": "hexagonal-bloc",
  "base_uri": "http://architecture.org/hexagonal-bloc",
  "prefix": "hbloc",
  "dependencies": [
    "hexagonal-architecture"
  ],
  "quad_store": {
    "engine": "sqlite-quad",
    "storage_path": "./lo_quads.db"
  },
  "named_graphs": {
    "canonical": "http://km.local/learning-ontologies/hexagonal-bloc/canonical",
    "governance": "http://km.local/learning-ontologies/hexagonal-bloc/governance"
  }
}
```

| Field          | Required | Description                                                                                                                      |
| :------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------- |
| `dependencies` | No       | Ordered list of prerequisite `ontology_id` strings. Default when omitted: `[]` (no declared prerequisites). MAY be empty (`[]`). |

### B.3.3 Semantics

1. **Direct dependencies only.** Each entry MUST be an `ontology_id` present in `{lo-root}/catalog.json`. The array lists **immediate** prerequisites; transitive prerequisites are computed by the resolver (§B.4) and cached automatically (§B.4.5).
2. **Automatic cache, not automatic binding.** Declaring `dependencies` does not add entries to `.km/config.json` → `learning_ontologies`. It declares which catalog LOs KM MUST materialize in `.km/lo-cache/{ontology-id}/` when the declaring LO is explicitly bound. Transitive dependencies of those prerequisites are cached recursively.
3. **`rootPath` + catalog required for auto-cache.** When `{lo-root}/catalog.json` is unavailable (no `rootPath` and inference fails per §B.2.4), only explicitly bound LOs are cached — base-spec behavior. Implementations MUST emit `catalog_not_found` or `rootPath_required_for_dependencies` when a bound LO declares non-empty `dependencies` but dependency cache resolution cannot run.
4. **Implicit entries are read-only.** Auto-cached dependency LOs are loaded with `mode: read_only` for runtime purposes (validation, query, schema). They do not grant curator MR rights unless the same `ontology_id` also appears as an **explicit** binding with `mode: curator`.
5. **Explicit binding overrides.** If an `ontology_id` appears both as a transitive dependency and as an explicit `learning_ontologies` entry, the explicit binding's `source` and `mode` take precedence for that LO; cache sync uses the explicit `source` path when paths differ.
6. **Self-reference forbidden.** An LO MUST NOT list its own `ontology_id` in `dependencies`.
7. **RDF alignment recommended.** When `dependencies` is non-empty, `exports/main.ttl` SHOULD include matching `owl:imports` triples pointing at the dependency's public ontology IRI (`base_uri`), and extension classes SHOULD use `rdfs:subClassOf` (or property chains) referencing dependency terms rather than redefining them.

### B.3.4 Empty and foundation ontologies

Foundation LOs with no upstream KM dependencies SHOULD set `"dependencies": []` explicitly or omit the key.

```json
{
  "ontology_id": "software-system",
  "base_uri": "http://architecture.org/software-system",
  "dependencies": [],
  "named_graphs": { "…": "…" }
}
```

---

## B.4 Dependency graph and cycle prevention

### B.4.1 Graph construction

Given a loaded catalog and all reachable LO package configs under `{lo-root}`:

1. Let **V** be the set of `ontology_id` values in `catalog.json`.
2. For each catalog entry **n**, load `{lo-root}/{path}/config.json` and read `dependencies` (default `[]`).
3. Add a directed edge **n → d** for each **d** in `dependencies`.

Edges MUST only point to nodes in **V**. An edge to an id not in the catalog is a **`unknown_dependency`** error (§B.5.3).

### B.4.2 Cycle detection algorithm

Before accepting catalog or workspace validation, implementations MUST detect directed cycles.

**Algorithm (depth-first search with three-color marking):**

```
COLORS: WHITE=unvisited, GRAY=in-stack, BLACK=done

for each node n in V:
  if color[n] == WHITE:
    if dfs(n) reports cycle: FAIL

dfs(n):
  color[n] = GRAY
  for each d in dependencies(n):
    if d not in V: return unknown_dependency
    if color[d] == GRAY: return cycle (d → … → n → d)
    if color[d] == WHITE and dfs(d) reports cycle: return cycle
  color[n] = BLACK
  return ok
```

On cycle detection, the error MUST include a **cycle path** (e.g. `hexagonal-bloc → hexagonal-architecture → hexagonal-bloc` is impossible if only bloc→hex; example cycle: `a → b → c → a`).

### B.4.3 Cycle errors are hard failures

| Context                       | Behavior                                                                                                               |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------- |
| Catalog / LO repo validation  | `catalog.json` and affected packages MUST NOT be considered valid until the cycle is removed.                          |
| `validate_bindings`           | Returns `valid: false` with `errors[]` describing the cycle; MCP `setup` MUST NOT reach `status: "ready"`.             |
| Curator `propose_semantic_mr` | If approving an MR would introduce a cycle (via changed `dependencies` in package config), reject the MR before merge. |

Implementations MAY validate cycles only over catalog entries referenced by **effective_cache_set(B)** plus their dependency nodes, but SHOULD validate the **full catalog** when `{lo-root}/catalog.json` is loaded at startup.

### B.4.4 Transitive closure

Define **closure(S)** as the set of all `ontology_id` values reachable from any node in set **S** by following `dependencies` edges (excluding nodes already in **S**).

For workspace **explicit binding set** **B** (the `ontology_id` values in `.km/config.json` → `learning_ontologies`):

```
effective_cache_set(B) = B ∪ closure(B)
```

| Set                        | Meaning                                                                                                             |
| :------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| **B**                      | LOs the workspace operator explicitly bound (config entries).                                                       |
| **closure(B)**             | Transitive dependencies of **B**, resolved via catalog + package `dependencies` arrays.                             |
| **effective_cache_set(B)** | Every LO whose canonical graph MUST be present in `.km/lo-cache/` and in the merged SHACL / query / schema runtime. |

### B.4.5 Transitive dependency cache resolution

When `{lo-root}` and `catalog.json` are available, MCP startup and LO cache sync MUST:

1. Compute **effective_cache_set(B)** from explicit bindings **B**.
2. For each `ontology_id` **id** in **effective_cache_set(B)**:
   *   If **id** ∈ **B**, resolve package path from the explicit binding's `source` (§B.2.3).
   *   If **id** ∈ **closure(B)** only (implicit dependency), resolve package path from catalog entry `{lo-root}/{path}/` (§B.1.3).
3. Sync `.km/lo-cache/{id}/lo_quads.db` from `{package}/exports/` for every **id** in **effective_cache_set(B)** — same checksum / rebuild rules as base §2.3.
4. Include every cached LO in **effective_cache_set(B)** in:
   *   SHACL shapes compilation (merged canonical graphs),
   *   default `query_semantic_graph` LO union,
   *   `km://schemas/learning-ontologies` (see §B.5.4).

**Single-binding example:** workspace binds only `hexagonal-bloc`; package declares `"dependencies": ["hexagonal-architecture"]`; `hexagonal-architecture` declares `"dependencies": ["software-system"]`. Then:

```
B = { hexagonal-bloc }
effective_cache_set(B) = { hexagonal-bloc, hexagonal-architecture, software-system }
```

Three cache directories are materialized; SHACL validation sees shapes and vocabulary from all three.

**Failure modes:** if any id in **effective_cache_set(B)** cannot be resolved to a valid package (missing catalog entry, missing `main.ttl`, cycle, or unknown dependency id), startup MUST fail — partial cache of only **B** is not permitted when dependency resolution was attempted.

When `catalog.json` is absent and inference fails, implementations cache **B** only and skip closure expansion (§B.8).

---

## B.5 Validation

### B.5.1 `validate_bindings` extensions

The MCP tool `validate_bindings` (base §3.1) is extended to perform dependency and catalog checks when `{lo-root}` can be resolved (via `rootPath` or inference per §B.2.4).

#### Extended response shape

```json
{
  "valid": true,
  "rootPath": "/abs/path/to/ontologies",
  "catalog_loaded": true,
  "explicit_bindings": ["hexagonal-bloc"],
  "effective_cache_set": [
    "hexagonal-bloc",
    "hexagonal-architecture",
    "software-system"
  ],
  "implicit_dependencies": [
    "hexagonal-architecture",
    "software-system"
  ],
  "bindings": [
    {
      "ontology_id": "hexagonal-bloc",
      "source": "/abs/path/to/ontologies/hexagonal-bloc",
      "mode": "read_only",
      "binding_kind": "explicit",
      "dependencies": ["hexagonal-architecture"],
      "cache_synced": true
    },
    {
      "ontology_id": "hexagonal-architecture",
      "source": "/abs/path/to/ontologies/hexagonal-architecture",
      "mode": "read_only",
      "binding_kind": "implicit",
      "dependencies": ["software-system"],
      "cache_synced": true
    }
  ],
  "errors": []
}
```

| Field                     | Description                                                          |
| :------------------------ | :------------------------------------------------------------------- |
| `rootPath`                | Resolved absolute LO repository root, or `null` if not determined.   |
| `catalog_loaded`          | Whether `{lo-root}/catalog.json` was loaded successfully.            |
| `explicit_bindings`       | Sorted `ontology_id` list from workspace `learning_ontologies`.      |
| `effective_cache_set`     | Sorted ids in **B ∪ closure(B)** that MUST be cached (§B.4.4).       |
| `implicit_dependencies`   | Sorted ids in **effective_cache_set** \ **B** (auto-cached only).    |
| `bindings[]`              | One entry per id in **effective_cache_set** after resolution.        |
| `bindings[].binding_kind` | `"explicit"` (config entry) or `"implicit"` (dependency-resolved).   |
| `bindings[].cache_synced` | Whether `.km/lo-cache/{ontology_id}/` is present and checksum-valid. |
| `errors[]`                | Structured errors (see §B.5.3).                                      |

When `valid: true`, every id in **effective_cache_set** MUST appear in `bindings[]` with `cache_synced: true`, and no error codes in §B.5.3 MAY be present.

### B.5.2 Catalog validation (`validate_lo_catalog`)

Implementations SHOULD expose catalog validation internally at MCP startup when `{lo-root}` is known. Checks:

1. Parse `catalog.json` against §B.1.3 schema.
2. Enforce catalog invariants (§B.1.4).
3. Build dependency graph; run cycle detection (§B.4.2).
4. For each catalog entry, verify package `config.json` → `ontology_id` matches catalog.

Failure prevents loading dependency metadata but SHOULD NOT prevent loading LO bindings whose `source` paths validate under base rules (implementation MAY treat full catalog failure as warning-only for backward compatibility during migration — see §B.8).

### B.5.3 Error codes

| Code                                 | Severity | Condition                                                                                               |
| :----------------------------------- | :------- | :------------------------------------------------------------------------------------------------------ |
| `catalog_not_found`                  | warning  | `{lo-root}` resolved but `catalog.json` missing; dependency cache expansion skipped; only **B** cached. |
| `catalog_invalid`                    | error    | `catalog.json` parse or schema failure when catalog load was required.                                  |
| `catalog_id_mismatch`                | error    | Catalog `ontology_id` ≠ package `config.json` for a listed path.                                        |
| `unknown_dependency`                 | error    | Package `dependencies[]` references id not in catalog.                                                  |
| `self_dependency`                    | error    | Package lists its own `ontology_id` in `dependencies`.                                                  |
| `dependency_cycle`                   | error    | Cycle detected in dependency graph; include `cycle_path[]`.                                             |
| `dependency_unresolvable`            | error    | Id in **effective_cache_set(B)** has no resolvable package path or missing `exports/main.ttl`.          |
| `rootPath_required_for_dependencies` | error    | Explicitly bound LO has non-empty `dependencies` but `{lo-root}` / catalog cannot be resolved.          |
| `multiple_lo_roots`                  | error    | Bindings imply more than one `{lo-root}` without `rootPath`.                                            |
| `rootPath_not_found`                 | error    | Configured `rootPath` does not exist or is not a directory.                                             |
| `cache_sync_failed`                  | error    | Cache rebuild for an id in **effective_cache_set(B)** failed.                                           |

Base specification binding errors (`ontology_id mismatch`, missing `main.ttl`, etc.) remain unchanged and compose with the above.

### B.5.4 `status` extensions

`status` (base §3.1) SHOULD include:

```json
{
  "lo_root": "/abs/path/to/ontologies",
  "catalog_ontology_count": 5,
  "explicit_bindings": ["hexagonal-bloc"],
  "effective_cache_set": [
    "hexagonal-bloc",
    "hexagonal-architecture",
    "software-system"
  ],
  "implicit_dependencies": [
    "hexagonal-architecture",
    "software-system"
  ],
  "dependency_validation": {
    "valid": true,
    "cache_sync_complete": true
  }
}
```

Each LO object inside `learning_ontologies` (base `status` shape) SHOULD gain `"binding_kind": "explicit" | "implicit"` when reported per cached LO. Implicit entries use catalog-resolved `source` paths and `mode: "read_only"`.

When `dependency_validation.valid` is `false` or `cache_sync_complete` is `false`, agents SHOULD call `validate_bindings` for details before ingesting case facts that reference cross-LO IRIs.

---

## B.6 Recommended layering pattern

Addendum 2 does not mandate a specific foundation ontology, but repositories SHOULD adopt this curation pattern:

```mermaid
flowchart TB
  SS[software-system<br/>dependencies: []]
  HEX[hexagonal-architecture<br/>dependencies: software-system]
  HB[hexagonal-bloc<br/>dependencies: hexagonal-architecture]
  DP[defensive-programming<br/>dependencies: software-system]
  SS --> HEX
  SS --> DP
  HEX --> HB
```

| Layer                  | Role                                       | `dependencies`                               |
| :--------------------- | :----------------------------------------- | :------------------------------------------- |
| Foundation             | Owns generic software terms                | `[]`                                         |
| Architecture / pattern | Extends foundation with pattern vocabulary | `["software-system"]` or other foundation id |
| Application profile    | Extends one or more pattern LOs            | e.g. `["hexagonal-architecture"]`            |

Workspace binding for the diagram above when using only `hexagonal-bloc`:

```json
{
  "rootPath": "../ontologies",
  "learning_ontologies": [
    { "ontology_id": "hexagonal-bloc", "source": "hexagonal-bloc", "mode": "read_only" }
  ]
}
```

KM computes **effective_cache_set(B) = { hexagonal-bloc, hexagonal-architecture, software-system }** and caches all three. Explicit bindings for prerequisite LOs remain optional (e.g. to set `mode: curator` on `software-system` in a maintainer workspace).

---

## B.7 MCP startup sequence (amended)

When Addendum 2 is implemented, MCP startup (base §2.3, §3.2) MUST:

1. Load `.km/config.json`; resolve optional `rootPath` → `{lo-root}`.
2. If `{lo-root}/catalog.json` exists, validate catalog (§B.5.2) and build dependency graph.
3. Resolve each explicit binding `source` per §B.2.3; let **B** be the set of explicitly bound `ontology_id` values.
4. Compute **effective_cache_set(B)** (§B.4.4). When catalog is unavailable, **effective_cache_set(B) = B** only.
5. Run extended `validate_bindings` (§B.5.1); **fail fast** on `dependency_cycle`, `unknown_dependency`, `dependency_unresolvable`, or `rootPath_required_for_dependencies` when closure expansion was required.
6. For every **id** in **effective_cache_set(B)**, sync `.km/lo-cache/{id}/` from the resolved package path (explicit binding path or catalog `{path}`).
7. Compile SHACL cache and schema bundle from **all** LOs in **effective_cache_set(B)** — not from explicit bindings alone.

Dependency order does **not** change SHACL merge semantics (union of all cached LO shapes). Topological sort of dependencies MAY be used for cache sync logging and error reporting.

---

## B.8 Compatibility and migration

| Concern                           | Rule                                                                                                                                |
| :-------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| **Existing workspaces**           | Omitting `rootPath` and package `dependencies` preserves base behavior (cache **B** only).                                          |
| **Existing LO packages**          | `dependencies` optional; omitted means `[]`. Non-empty `dependencies` require resolvable `{lo-root}` + catalog for auto-cache.      |
| **Existing bindings**             | Absolute `source` paths continue to work unchanged.                                                                                 |
| **`owl:imports` in TTL**          | Unchanged; not parsed for cache expansion in v1 of Addendum 2 — `dependencies` in `config.json` is authoritative for cache closure. |
| **Duplicate explicit + implicit** | Same `ontology_id` in **B** and **closure(B)** uses explicit binding `source` and `mode`.                                           |

### Migration checklist for LO repository maintainers

1. Add `{lo-root}/catalog.json` listing all packages.
2. Add `"dependencies": []` or appropriate ids to each `{package}/config.json`.
3. Set `"rootPath"` in consumer workspace configs; shorten binding `source` to package-relative paths.
4. Remove redundant explicit bindings for prerequisite LOs where auto-cache suffices; keep explicit entries only when `mode: curator` or non-catalog `source` paths are needed.
5. Update package README **Dependencies** sections to match `dependencies` arrays (workspace config no longer needs to list prerequisites).

---

## B.9 Implementation phasing

| Phase  | Deliverable                                                                              | Unblocks                                           |
| :----- | :--------------------------------------------------------------------------------------- | :------------------------------------------------- |
| **P1** | `catalog.json` schema + parser; `dependencies` field on `LOPackageConfig`                | Declarative metadata in repo                       |
| **P2** | Workspace `rootPath`; amended `source` resolution (§B.2.3)                               | Ergonomic bindings against a shared LO repo        |
| **P3** | Cycle detection + `unknown_dependency` validation on catalog load                        | Safe extension hierarchies                         |
| **P4** | **effective_cache_set** resolver + transitive LO cache sync                              | Single-binding workspaces get full SHACL closure   |
| **P5** | Extended `validate_bindings` / `status` fields (`implicit_dependencies`, `binding_kind`) | Observability; ontologies repo `catalog.json` seed |

P1–P3 can ship without breaking existing workspaces. P4 changes runtime cache behavior when `rootPath`, catalog, and non-empty `dependencies` are all present.

---

## B.10 Summary of config changes

### Workspace `.km/config.json`

| Key        | Status            | Description                                           |
| :--------- | :---------------- | :---------------------------------------------------- |
| `rootPath` | **New, optional** | Path to LO repository root containing `catalog.json`. |

### LO repository `{lo-root}/catalog.json`

| Key         | Status                                             | Description                                 |
| :---------- | :------------------------------------------------- | :------------------------------------------ |
| Entire file | **New, required when using dependency validation** | Registry of `ontology_id` → package `path`. |

### LO package `{source}/config.json`

| Key            | Status            | Description                                                                                                          |
| :------------- | :---------------- | :------------------------------------------------------------------------------------------------------------------- |
| `dependencies` | **New, optional** | Prerequisite `ontology_id` strings; default `[]`. Triggers transitive auto-cache when catalog is available (§B.4.5). |

### Runtime cache (amended base §2.3)

| Behavior                  | Rule                                                                          |
| :------------------------ | :---------------------------------------------------------------------------- |
| **Explicit bindings**     | LOs listed in `learning_ontologies` (**B**).                                  |
| **Implicit dependencies** | Transitive closure **closure(B)** resolved via catalog; cached automatically. |
| **Cache target**          | `.km/lo-cache/{id}/` for every **id** in **effective_cache_set(B)**.          |

---

*End of Addendum 2*
