# Knowledge Management System Specification — Addendum 3

**OWL import scaffolding and LO package bootstrap**

This document is **Addendum 3** to [knowledge-management-specification.md](./knowledge-management-specification.md). It specifies a CLI workflow for importing external OWL/RDF ontologies into the Learning Ontology (LO) repository package layout, materializing `exports/main.ttl`, generating package `config.json`, and registering the package in `catalog.json`.

Addendum 3 is normative where it defines CLI behavior, inference rules, and filesystem artifacts. Unchanged behavior in the base specification and [Addendum 1](./knowledge-management-specification-add-1.md) / [Addendum 2](./knowledge-management-specification-add-2.md) remains authoritative unless explicitly superseded below.

---

## C.0 Motivation and scope

### C.0.1 Problem statement

Addendum 2 (§B.0.4) deferred **import/scaffold tooling** — operators must hand-author LO packages when adopting external vocabularies. The ontologies repository already holds raw OWL sources under `sources/` (e.g. `swo-full.owl`) that are not yet bindable LO packages.

Without import tooling, teams encounter:

| Failure mode                 | Symptom                                                                                   | Current workaround (undesired)                                     |
| :--------------------------- | :---------------------------------------------------------------------------------------- | :----------------------------------------------------------------- |
| **Manual package bootstrap** | Curator copies OWL into ad-hoc paths; `config.json` and `catalog.json` drift              | Hand-edit JSON and Turtle; inconsistent layout                     |
| **Format friction**          | Source ontology is RDF/XML or remote URL; KM cache sync expects Turtle `exports/main.ttl` | One-off `rapper`/`riot` commands; forgotten in CI                  |
| **Lost dependency signal**   | Source declares `owl:imports` but `config.json` → `dependencies` is empty                 | SHACL closure incomplete until Addendum 2 deps are hand-maintained |
| **Identifier mismatch**      | `ontology_id`, Turtle prefix, and `base_uri` disagree across files                        | Agents emit wrong IRIs; `validate_bindings` catalog checks fail    |

### C.0.2 Rationale for importing OWL

**Reuse published domain knowledge.** Many domains already maintain OWL ontologies (OBO, LOV, domain-specific archives). KM SHOULD scaffold LO packages from those sources instead of re-encoding vocabulary by hand — preserving authoritative IRIs, labels, and axiom structure.

**Normalize to the LO export contract.** The MCP imports Git-tracked `exports/main.ttl` into workspace cache (base §2.3–2.4). External OWL files in arbitrary serializations or at HTTP URLs are not directly bindable. Import tooling converts the source graph into the canonical Turtle export format KM already understands.

**Bootstrap Addendum 2 metadata.** Imported ontologies often declare `owl:imports`. The importer SHOULD map resolvable import IRIs to catalog `ontology_id` values and emit matching `dependencies` arrays — aligning operational cache closure (Addendum 2 §B.3) with semantic import declarations.

**Lower curator onboarding cost.** A single CLI invocation from the LO repository root produces directory layout, `config.json`, `exports/main.ttl`, stub `README.md`, governance placeholder, and a `catalog.json` entry — ready for SHACL extension and semantic MR curation.

**Non-destructive staging.** Import creates a **new** package directory under the operator's current working directory. It does not mutate workspace `.km/config.json` or existing packages unless the operator re-runs import targeting an existing `id` (see §C.4.6).

### C.0.3 In-scope additions

| ID     | Addition                                       | Addresses                                                 |
| :----- | :--------------------------------------------- | :-------------------------------------------------------- |
| **C1** | `km import-lo` CLI subcommand                  | Scripted LO package bootstrap from file or URL            |
| **C2** | RDF parse + Turtle serialization pipeline      | OWL/XML, RDF/XML, Turtle, N-Triples, JSON-LD → `main.ttl` |
| **C3** | Automatic `ontology_id` and `prefix` inference | Sensible defaults when `--id` / `--prefix` omitted        |
| **C4** | LO package directory scaffold                  | Standard layout per base §2.4                             |
| **C5** | `catalog.json` upsert at repository root       | Registry stays authoritative (Addendum 2 §B.1)            |
| **C6** | `owl:imports` → `dependencies` mapping         | Best-effort resolution against existing catalog entries   |

### C.0.4 Out of scope (deferred)

*   OWL DL reasoning, materialization of entailed axioms, or import closure merging into a single flattened ontology (imported `main.ttl` reflects **asserted** triples from the source document only).
*   Automatic SHACL shape generation from OWL class expressions.
*   Workspace binding (`learning_ontologies` / `rootPath`) — operator binds after import via `km init` or manual config edit.
*   Downloading and vendoring transitive `owl:imports` closure as separate LO packages in one command (operator may run `import-lo` per import).
*   MCP tool equivalent (`import_lo` over stdio) — CLI first; MCP MAY follow in a later revision.

---

## C.1 CLI command

### C.1.1 Invocation

The importer runs against the **process current working directory** (`cwd`). In typical usage, `cwd` is the LO repository root (the directory containing or intended to contain `catalog.json`).

```bash
km import-lo <file|url> [--prefix <prefix>] [--id <id>]
```

| Argument   | Required | Description                                                                                                                   |
| :--------- | :------- | :---------------------------------------------------------------------------------------------------------------------------- |
| `<source>` | Yes      | Positional: filesystem path to an ontology file **or** HTTP/HTTPS URL. Relative paths resolve against `cwd`.                  |
| `--prefix` | No       | Turtle/QName prefix for the domain vocabulary (e.g. `hex`). MUST NOT include trailing `:`. When omitted, inferred per §C.3.2. |
| `--id`     | No       | LO package `ontology_id` slug (e.g. `hexagonal-architecture`). When omitted, inferred per §C.3.1.                             |

**Exit codes:**

| Code | Meaning                                                         |
| :--- | :-------------------------------------------------------------- |
| `0`  | Package scaffolded; `catalog.json` updated                      |
| `1`  | Parse error, I/O failure, validation error, or catalog conflict |
| `2`  | Feature not implemented (pre-Addendum-3 builds)                 |

### C.1.2 Working directory semantics

| Symbol           | Definition                                                                                              |
| :--------------- | :------------------------------------------------------------------------------------------------------ |
| `cwd`            | `Path.cwd()` at command start — **not** the application workspace root unless the operator `cd`'s there |
| `{package-root}` | `cwd / <id>`                                                                                            |
| `{lo-root}`      | `cwd` when `catalog.json` exists or is created at `cwd/catalog.json`                                    |

The command MUST NOT require an initialized `.km/` workspace. It operates on the LO source repository filesystem only.

---

## C.2 Source ingestion

### C.2.1 Supported inputs

| Input kind      | Examples                                      | Rules                                     |
| :-------------- | :-------------------------------------------- | :---------------------------------------- |
| **Local file**  | `./sources/swo-full.owl`, `/tmp/ontology.ttl` | MUST exist and be readable                |
| **HTTP(S) URL** | `https://example.org/onto.owl`                | GET with redirect follow; fail on non-2xx |

### C.2.2 Supported RDF serializations

Implementations MUST detect format by file extension, `Content-Type` (URLs), or sniffing and MUST accept at minimum:

*   RDF/XML (`.owl`, `.rdf`, `.xml`)
*   Turtle (`.ttl`)
*   N-Triples (`.nt`)
*   JSON-LD (`.jsonld`, `.json`)
*   OWL/XML (when distinguishable from RDF/XML)

On parse failure, the command MUST exit non-zero and print the parser error without creating partial directories (transactional directory creation — §C.4.7).

### C.2.3 HTTP fetch policy

When `<source>` is a URL:

1. Use HTTPS preferred; HTTP allowed.
2. Follow redirects (max 5).
3. Timeout: 60 seconds connect + read (configurable constant).
4. Set a descriptive `User-Agent` (e.g. `km-import-lo/{version}`).
5. Persist optional provenance comment in generated `README.md` (source URL, fetch timestamp).

Implementations MUST NOT execute non-HTTP(S) schemes (`file://` URLs SHOULD be rejected in favor of local paths).

---

## C.3 Identifier inference

When `--id` and/or `--prefix` are omitted, the implementation derives values from the parsed ontology graph and input metadata.

### C.3.1 `ontology_id` (`--id`)

**Priority order** (first successful rule wins):

1. **Explicit `--id`** — use as-is after validation (§C.3.3).
2. **`owl:Ontology` about URI** — if exactly one ontology header exists, take the last non-empty path segment of the ontology IRI, slugified:
    *   `http://architecture.org/hexagonal` → `hexagonal`
    *   `http://www.ebi.ac.uk/swo/swo/swo-full.owl` → `swo-full`
3. **Local filename** — basename without extension, slugified:
    *   `sources/swo-full.owl` → `swo-full`
4. **URL path** — last path segment without extension when input is URL.

**Slugification rules:**

*   Lowercase ASCII.
*   Replace spaces and underscores with `-`.
*   Strip characters outside `[a-z0-9-]`.
*   Collapse consecutive `-`; trim leading/trailing `-`.
*   MUST match `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$` or fail with `invalid_ontology_id`.

If multiple `owl:Ontology` headers exist and `--id` was not provided, the command MUST fail with `ambiguous_ontology_id` unless all headers share the same slugifiable identity.

### C.3.2 `prefix` (`--prefix`)

**Priority order:**

1. **Explicit `--prefix`** — use without trailing `:`.
2. **Preferred namespace from parser** — default namespace or `xml:base` local name when present and valid as a Turtle prefix (`^[a-zA-Z][a-zA-Z0-9_-]*$`).
3. **Derived from `ontology_id`** — compress slug to initials or truncate to 8 chars (e.g. `hexagonal-architecture` → `hexarch`); implementation MAY use a small heuristic table but MUST document the algorithm.
4. **Fallback** — first segment of `ontology_id` before `-` (e.g. `swo-full` → `swo`).

### C.3.3 `base_uri`

Always derived from the ontology header when available:

*   Use the `owl:Ontology` subject IRI (with fragment stripped unless the IRI ends with `#`).
*   When no ontology header exists, synthesize: `http://km.local/imported/{ontology_id}` and emit a warning `synthetic_base_uri`.

`base_uri` MUST NOT include a trailing `#` unless the source ontology IRI uses hash style consistently.

### C.3.4 Validation constraints

| Field         | Rule                                                                                                              |
| :------------ | :---------------------------------------------------------------------------------------------------------------- |
| `ontology_id` | Unique among `catalog.json` → `ontologies[].ontology_id` unless `--force` (future) or operator confirms overwrite |
| `prefix`      | Unique among existing packages' `config.json` → `prefix` in `cwd` (warning only if duplicate)                     |
| `base_uri`    | Logged; no uniqueness requirement                                                                                 |

---

## C.4 Filesystem effects

### C.4.1 Package directory layout

The command creates `{package-root} = cwd / <id>` with this structure (aligned with base §2.4 and ontologies repo README):

```
cwd/
├── catalog.json                     # Created or updated (§C.5)
└── <id>/
    ├── README.md                    # Generated import provenance stub
    ├── config.json                  # Generated (§C.4.2)
    └── exports/
        ├── main.ttl                 # Serialized ontology (§C.4.3)
        └── governance/
            └── .gitkeep             # Placeholder for future MR records
```

`lo_quads.db` MUST NOT be created or committed — runtime store per base §2.4.

### C.4.2 Generated `config.json`

```json
{
  "ontology_id": "<id>",
  "base_uri": "<base_uri>",
  "prefix": "<prefix>",
  "dependencies": ["<resolved-import-id>", "..."],
  "quad_store": {
    "engine": "sqlite-quad",
    "storage_path": "./lo_quads.db"
  },
  "named_graphs": {
    "canonical": "http://km.local/learning-ontologies/<id>/canonical",
    "governance": "http://km.local/learning-ontologies/<id>/governance"
  }
}
```

| Field          | Source                                    |
| :------------- | :---------------------------------------- |
| `ontology_id`  | Resolved `<id>`                           |
| `base_uri`     | §C.3.3                                    |
| `prefix`       | Resolved `<prefix>`                       |
| `dependencies` | §C.4.4                                    |
| `named_graphs` | Template from `ontology_id` per base §2.5 |

### C.4.3 Generated `exports/main.ttl`

The implementation MUST:

1. Parse the source graph.
2. Serialize **asserted triples** from the source document to Turtle at `{package-root}/exports/main.ttl`.
3. Emit standard prefix declarations at the top, including at minimum:
    *   `rdf`, `rdfs`, `owl`, `xsd`
    *   `{prefix}:` → `{base_uri}#` or `{base_uri}/` consistent with term IRIs in the graph
4. Preserve `owl:Ontology` header triples when present.
5. Preserve `owl:imports` declarations in Turtle (Addendum 2 §B.3.3 recommends RDF alignment).
6. Use UTF-8 encoding and POSIX newlines.

**SHACL:** Imported ontologies may not include SHACL shapes. Empty shape sections are valid; curators add shapes via semantic MR workflow later.

**Comments:** Implementations MAY prepend a generated comment block documenting import source path/URL and ISO-8601 timestamp. Generated comments MUST NOT alter RDF semantics.

### C.4.4 `dependencies` from `owl:imports`

For each object of `owl:imports` on the ontology header (or ontology node):

1. Resolve import IRI to a string form.
2. If `cwd/catalog.json` exists, match import IRI against known packages:
    *   Compare to each catalog entry's package `config.json` → `base_uri` (exact or normalized trailing `/` / `#`).
    *   Compare to ontology IRI in existing `exports/main.ttl` `owl:Ontology` subject.
3. On match, append the matched `ontology_id` to `dependencies` (deduplicated, stable sort).
4. On no match, omit from `dependencies` and record in stdout/stderr as `unresolved_import: <iri>` (non-fatal).

Self-imports MUST be ignored. Cycles introduced only via `dependencies` are caught later by Addendum 2 catalog validation — the importer SHOULD warn when a new edge would create a cycle.

### C.4.5 Generated `README.md`

Minimal stub:

```markdown
# <label or ontology_id>

Imported Learning Ontology package scaffold.

- **Source:** <file path or URL>
- **Imported at:** <ISO-8601 timestamp>
- **ontology_id:** `<id>`
- **base_uri:** `<base_uri>`
- **prefix:** `<prefix>`

## Next steps

1. Review `exports/main.ttl` vocabulary and add SHACL shapes as needed.
2. Confirm `dependencies` in `config.json` against `owl:imports`.
3. Expand this README with domain documentation and case-fact examples.
4. Bind from a workspace via `.km/config.json` or `km init --lo-source <path-to-this-package>`.
```

### C.4.6 Collision and overwrite policy

| Condition                           | Default behavior                                                                                        |
| :---------------------------------- | :------------------------------------------------------------------------------------------------------ |
| `cwd/<id>/` does not exist          | Create package                                                                                          |
| `cwd/<id>/` exists                  | **Fail** with `package_exists` — do not partially overwrite                                             |
| `catalog.json` already lists `<id>` | **Fail** with `catalog_id_exists` unless package path matches and operator passes future `--force` flag |

### C.4.7 Atomicity

Directory creation MUST be transactional:

1. Parse and serialize to a temporary file.
2. On success, create directories and move temp file to `exports/main.ttl`.
3. Write `config.json`, `README.md`, `.gitkeep`.
4. Update `catalog.json` last.
5. On any failure after step 2 begins, remove created `{package-root}` tree if this invocation created it.

---

## C.5 Catalog update (`catalog.json`)

### C.5.1 Location

`catalog.json` at `cwd/catalog.json` — consistent with Addendum 2 §B.1.2.

### C.5.2 Create

When `catalog.json` is absent, create:

```json
{
  "catalog_version": "1",
  "ontologies": [
    {
      "ontology_id": "<id>",
      "path": "<id>",
      "label": "<label>"
    }
  ]
}
```

### C.5.3 Update

When `catalog.json` exists:

1. Parse per Addendum 2 §B.1.3 schema.
2. If `<id>` not present, append a new entry:
    *   `ontology_id`: `<id>`
    *   `path`: `<id>` (relative to `cwd`)
    *   `label`: from `rdfs:label` on `owl:Ontology` when available; else title-cased `<id>` with hyphens as spaces
3. Preserve existing entries unchanged.
4. Re-validate catalog invariants (§B.1.4) before write; on failure, abort without writing.

### C.5.4 Sorting

Implementations MAY sort `ontologies[]` by `ontology_id` ascending for stable diffs.

---

## C.6 End-to-end algorithm

```
import_lo(source, prefix?, id?):
  graph, meta = parse(source)                    # §C.2
  id = id ?? infer_ontology_id(graph, meta)      # §C.3.1
  prefix = prefix ?? infer_prefix(graph, id)       # §C.3.2
  base_uri = infer_base_uri(graph, id)             # §C.3.3
  validate_id_unique(id, cwd/catalog.json)       # §C.4.6

  package_root = cwd / id
  assert not package_root.exists()

  turtle = serialize_turtle(graph, prefix, base_uri)  # §C.4.3
  deps = resolve_import_dependencies(graph, cwd)      # §C.4.4

  atomically:
    create package_root/exports/governance/.gitkeep
    write package_root/exports/main.ttl
    write package_root/config.json
    write package_root/README.md
    upsert_catalog(cwd/catalog.json, id, label(graph))  # §C.5

  print summary(id, prefix, base_uri, deps, package_root)
```

---

## C.7 Examples

### C.7.1 Import local OWL from `sources/`

```bash
cd /path/to/ontologies
km import-lo ./sources/swo-full.owl
```

**Inferred (illustrative):**

| Field      | Value                                       |
| :--------- | :------------------------------------------ |
| `id`       | `swo-full`                                  |
| `prefix`   | `swo`                                       |
| `base_uri` | `http://www.ebi.ac.uk/swo/swo/swo-full.owl` |

**Creates:**

```
ontologies/
├── catalog.json          # swo-full entry appended
└── swo-full/
    ├── README.md
    ├── config.json
    └── exports/
        ├── main.ttl
        └── governance/.gitkeep
```

### C.7.2 Import with explicit identity

```bash
cd /path/to/ontologies
km import-lo ./sources/dev.nemo.inf.ufes.br_seon.owl \
  --id seon \
  --prefix seon
```

### C.7.3 Import from URL

```bash
cd /path/to/ontologies
km import-lo https://www.w3.org/2002/07/owl.owl
```

---

## C.8 Validation after import

The importer does not invoke MCP. Operators SHOULD verify:

```bash
# From a maintainer workspace with rootPath pointing at the LO repo
km mcp   # reconnect; validate_bindings should list the new ontology when bound

# Or catalog-only checks (implementation-specific)
km status
```

Addendum 2 `validate_bindings` / catalog validation (§B.5.2) applies once the package is bound or when validating the full catalog at MCP startup.

---

## C.9 Error codes

| Code                    | Condition                                            |
| :---------------------- | :--------------------------------------------------- |
| `source_not_found`      | Local path does not exist                            |
| `fetch_failed`          | URL returned error or timed out                      |
| `parse_error`           | RDF parser failure                                   |
| `invalid_ontology_id`   | Inferred or supplied `id` fails slug rules           |
| `ambiguous_ontology_id` | Multiple ontology headers; `--id` required           |
| `package_exists`        | `cwd/<id>/` already present                          |
| `catalog_id_exists`     | `ontology_id` already in catalog with different path |
| `catalog_invalid`       | Existing `catalog.json` fails schema parse           |
| `catalog_write_failed`  | Could not write updated catalog                      |
| `synthetic_base_uri`    | Warning only — no ontology header found              |

---

## C.10 Relationship to Addendum 2

| Addendum 2 topic                           | Addendum 3 interaction                                                                                                                    |
| :----------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `catalog.json` registry (§B.1)             | Importer creates/updates entries                                                                                                          |
| `dependencies` (§B.3)                      | Populated from resolvable `owl:imports`                                                                                                   |
| `owl:imports` operational authority (§B.8) | Unchanged for cache closure — `dependencies` in generated `config.json` is authoritative for KM; `owl:imports` in `main.ttl` SHOULD align |
| Deferred import tooling (§B.0.4)           | **Superseded** by this addendum for CLI scaffold                                                                                          |

---

## C.11 Implementation phasing

| Phase  | Deliverable                                                       | Unblocks                                 |
| :----- | :---------------------------------------------------------------- | :--------------------------------------- |
| **P1** | `km import-lo` argparse + local Turtle/RDF/XML parse → `main.ttl` | Manual bootstrap removal for local files |
| **P2** | URL fetch + JSON-LD / N-Triples + inference (§C.3)                | Remote ontology adoption                 |
| **P3** | `config.json` + directory scaffold + `README.md` stub             | Bindable LO packages                     |
| **P4** | `catalog.json` upsert + `owl:imports` → `dependencies`            | Addendum 2 catalog integration           |
| **P5** | Transactional writes + structured error codes (§C.9)              | Safe CI / agent automation               |

---

## C.12 Summary of artifacts

| Artifact                               | Action                                                                                             |
| :------------------------------------- | :------------------------------------------------------------------------------------------------- |
| `cwd/<id>/config.json`                 | **Created** with `ontology_id`, `base_uri`, `prefix`, `dependencies`, `quad_store`, `named_graphs` |
| `cwd/<id>/exports/main.ttl`            | **Created** — Turtle serialization of source ontology                                              |
| `cwd/<id>/exports/governance/.gitkeep` | **Created**                                                                                        |
| `cwd/<id>/README.md`                   | **Created** — provenance stub                                                                      |
| `cwd/catalog.json`                     | **Created or updated** — new `ontologies[]` entry                                                  |
| `cwd/.km/config.json`                  | **Unchanged** — workspace binding is operator responsibility                                       |

---

*End of Addendum 3*
