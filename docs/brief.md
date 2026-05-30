# Brief

The **Knowledge Management MCP** is a neuro-symbolic bridge designed to capture the "How" (processes, rationale, exceptions) and the "What" of problem analysis and design. It operates on a version-controlled semantic **quad-store** hyper-graph utilizing a dual-ontology design, with validation and integrity constraints enforced via **SHACL (Shapes Constraint Language)**:

**Terminology**

1. **The Learning Ontologies:** Ontology of ontologies to capture the "How" of knowledge domains.
2. **The Case Ontology:** Local, dynamic, and situational realities derived from problem analysis and design. *(singular — one Case Ontology per workspace)*

KM is MCP tool for managing agent knowledge/memory to prevent hallucination and provide clearer context

## The Learning Ontologies

Learning ontologies are collection of knowledge organized or categorized by domain. Each learning ontology:
- Lives in a **self-contained source package** at an arbitrary filesystem path (sibling repo, submodule, system path, etc.) — not required to be inside the workspace
- Referenced by the workspace via an **object binding** in `.km/config.json` (`ontology_id`, `source`, `mode`)
- Materialized locally in `.km/lo-cache/{ontology-id}/` for runtime validation and query
- A `README.md` file in the source package that describes the purpose of the ontology
- Git-tracked Turtle exports in `{source}/exports/main.ttl` (canonical state) and `{source}/exports/governance/{mr-id}.ttl` (one file per MR record); database files are runtime-only and Git-ignored
- Should be self contained with all neccessary classes and relationship and can be used independently
- Agents validate and query against the **cached canonical named graph only**; pending MR proposal graphs are excluded

Adding knowledge to the learning ontology involves the following steps:
1. Identify new concepts and relationships.
2. Create a merge request with a semantic diff — recorded in the **source** LO governance graph and a proposal named graph inside `{source}/lo_quads.db` (requires `mode: "curator"` on the binding).
3. Human reviews and approves the merge request (via derived review document at `.km/mrs/` or `km://mr/{ontology-id}/{mr-id}`).
4. The canonical graph is updated only after approval; `{source}/exports/main.ttl` is regenerated and the MR's `{source}/exports/governance/{mr-id}.ttl` is updated; workspace cache is fully rebuilt on approve/reject only (not on propose).

> [!NOTE]
> **Domain-Specific Merge Requests:** A "Merge Request" (MR) within the KM system is an *internal, semantic-level concept* rather than a Git/GitHub/GitLab hosting platform PR/MR. While it conceptually mirrors the propose-review-approve-merge lifecycle, it is executed and tracked entirely within the target Learning Ontology's quad-store governance graph.
> 
> *   **Authoritative Record:** Each MR is stored as RDF triples in the LO governance named graph (`http://km.local/learning-ontologies/{id}/governance`) with proposal quads in a dedicated MR graph. Git-tracked `exports/governance/{mr-id}.ttl` mirrors each MR record.
> *   **Review Document (Derived):** A human-readable markdown view is generated at `.km/mrs/mr-<mr-id>.md` containing:
>     1.  **Summary of Changes:** Metadata (including the **exact approval command** to run, target ontology, author, and date), engineering rationale, targeted concepts, and high-level structural impact.
>     2.  **Detailed Changes:** The exact technical diff specifying the RDF `diff_insertions` and `diff_deletions` in Turtle serialization (diffed against `exports/main.ttl`).
> *   **Human Approval Interface:** The approval is finalized by the human developer issuing the explicit command/prompt:
>     ```
>     approve <doc name>
>     ```
>     *(e.g., `approve km://mr/react-conventions/MR-042` or `approve .km/mrs/mr-react-conventions-042.md`)*
> 
>     The agent translates this command into an `approve_semantic_mr` MCP tool call (see MCP Tools below).

## The Case Ontology

The Case Ontology:
- **Runtime:** `.km/case_quads.db` (Git ignored)
- **Git authority:** `case-exports/` at the workspace root (`graphs/` per branch, `governance/` per merge/audit event) — same export model as LO (see spec §2.6)
- References learning ontologies via **object bindings** in `.km/config.json`, not by requiring LO directories in the workspace tree
- Has knowledge related to the current problem/case being solved, including the facts, concepts, relationship, rules and process being applied
- Each "how" knowledge i.e. the "how" part of the solution should be linked to the related learning ontologies knowledge
- It is allowed to add exception for not following a learning ontology knowledge, with proper documentation and rationale
- Constructed as quad-store to allow named graph according to the repository branch

Human can initiate promoting knowledge from the case ontology to learning ontologies which will be handled as a merge request to the learning ontology (requires `mode: "curator"` on the target binding).

#### Workspace LO Binding Example (`.km/config.json`)
```json
{
  "learning_ontologies": [
    {
      "ontology_id": "react-conventions",
      "source": "../km-org-ontologies/react-conventions",
      "mode": "read_only"
    }
  ],
  "lo_cache": { "base_path": "./.km/lo-cache" },
  "case_exports": { "base_path": "./case-exports", "export_policy": "on_commit" }
}
```

## Knowledge Lifecycle & Evolution

Human can review the learning ontology periodically and decide to refactor, update, deprecate or archive any part of the ontology. This action should be performed through merge request.

## Governance & Human-in-the-Loop

Who owns, validates, and authors the semantic graph?
- **Case Fact Ingestion:** The agent dynamically discovers and registers facts during runtime.
- **Exception Authority:** The agent can self-declare local exceptions, but all exceptions require explicit human authorization before execution.
- **Curation Boundaries:** Individual developer maintains the Learning Ontologies.

## Version Control & State Synchronization

Learning Ontologies and the Case Ontology share the same **runtime vs export** pattern: Git-ignored quad-stores for MCP performance; Git-tracked Turtle exports for review and audit.

| Layer                  | Runtime (Git ignored)           | Git authority (tracked)                                                   | Export triggers                                                          |
| :--------------------- | :------------------------------ | :------------------------------------------------------------------------ | :----------------------------------------------------------------------- |
| **Learning Ontology**  | `{source}/lo_quads.db`          | `{source}/exports/main.ttl`, `exports/governance/{mr-id}.ttl`             | MR propose (governance shard); MR approve (main + governance)            |
| **Case Ontology**      | `.km/case_quads.db`             | `case-exports/graphs/{ref}.ttl`, `case-exports/governance/{event-id}.ttl` | Ingest (per `export_policy`); exception approve; branch merge resolution |
| **LO workspace cache** | `.km/lo-cache/{id}/lo_quads.db` | — (synced from LO source exports)                                         | LO MR approve/reject                                                     |

- **Source package** (`{source}/`): `lo_quads.db` is runtime-only; `exports/` is Git authority.
- **Case exports** (`case-exports/`): committed in the **application repo** alongside source code.
- **Workspace runtime** (`.km/`): `config.json`, `case_quads.db`, `lo-cache/`, derived `mrs/` — Git ignored.
- **Workspace cache** (`.km/lo-cache/{ontology-id}/`): synced from LO source exports on startup.
- **Bindings** specify `ontology_id`, `source` path, and `mode` (`read_only` or `curator`).

- **Branch Switch Detection:** watch `.git/HEAD`
- **Branch Inheritance & Fallback Logic:** The case ontology is cloned from the parent branch when a new branch is created (optional export of new branch graph file).
- **Workspace Portability & Porting:** Clone the repo and commit `case-exports/` to restore audit and branch snapshots; optionally copy `.km/` for a warm runtime cache.
- **Branch Merging Logic:** The system monitors Git state changes (via `.git/refs/` and `.git/HEAD`). Case graph sync follows `branch_merge.policy` in `.km/config.json`. Merge resolutions are recorded in `case-exports/governance/`. With committed exports, approved exceptions and merge decisions remain auditable in Git even when runtime `DELETE` clears branch graphs; without exports, recovery requires `.km` backup (see spec §5.3).

## Conflict Resolution & Validation

How are logical contradictions and rule violations managed?
- **Cross-Ontology Contradictions:** Human should review and resolve contradictions. The system should flag these contradictions to the human for review.
- **Constraint Enforcement (SHACL):** The system acts as a hard "linter" powered by **SHACL (Shapes Constraint Language)** shapes from LO **canonical graphs**, validating graph states and halting agent execution on un-excepted constraint violations. Pending MR proposal graphs never participate in validation.

## MCP Server Interface

The KM MCP Server exposes eight Tools and six Resources to the host agent, enabling seamless reading, writing, validation, and human-in-the-loop control of the semantic graph.

### 1. MCP Tools

| Tool Name                 | Parameters                                                                                           | Returns                                                                                                                                                   | Description                                                                                                                                                                       |
| :------------------------ | :--------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ingest_case_facts`       | `facts` (JSON-LD or Turtle string), `format` (string)                                                | `{ "status": "success", "triples_added": int }`                                                                                                           | Ingests new contextual facts, concepts, and relationships from the active case into the named graph mapped to the active branch.                                                  |
| `validate_constraints`    | *None*                                                                                               | `{ "conforms": bool, "violations": [Violation] }`                                                                                                         | Runs SHACL validation on the active named graph against shapes from LO **canonical graphs** only. Halts execution if violations are found and no approved local exception exists. |
| `propose_local_exception` | `bypasses_shape` (URI), `target_node` (URI), `rationale` (string)                                    | `{ "exception_id": URI, "status": "PENDING_APPROVAL" }`                                                                                                   | Declares a local exception to bypass a specific SHACL shape for a given focus node. Returns details so the agent can prompt the human developer.                                  |
| `approve_local_exception` | `exception_id` (URI), `approver` (string), `signature` (string)                                      | `{ "status": "APPROVED", "timestamp": string }`                                                                                                           | Records human approval signature and timestamp, enabling the SHACL linter to bypass the specified shape constraint.                                                               |
| `query_semantic_graph`    | `query` (SPARQL query string)                                                                        | SPARQL Select/Ask Result (JSON)                                                                                                                           | Executes a read-only SPARQL query over the merged active Case named graph and LO **canonical graphs** only.                                                                       |
| `propose_semantic_mr`     | `target_ontology` (URI), `rationale` (string), `diff_insertions` (Turtle), `diff_deletions` (Turtle) | `{ "mr_id": URI, "status": "PENDING_APPROVAL" }`                                                                                                          | Creates a semantic MR in the **source** LO store (requires `mode: "curator"`); generates a derived review document in `.km/mrs/`.                                                 |
| `get_system_status`       | *None*                                                                                               | `{ "active_branch": string, "learning_ontologies": [Binding], "pending_exceptions_count": int, "pending_mrs_count": int, "branch_merge_policy": string }` | Includes effective `branch_merge.policy` (`auto_merge_exception` default). `pending_mrs_count` from **source** governance graphs.                                                 |
| `approve_semantic_mr`     | `doc_identifier` (string)                                                                            | `{ "status": "APPROVED", "mr_id": URI, "target_ontology": URI, "timestamp": string }`                                                                     | Merges in **source** LO store (requires `mode: "curator"`), regenerates source exports, refreshes workspace cache, reloads in-memory LO cache.                                    |

### 2. MCP Resources

The server exposes read-only structural data to the host agent to clarify schema definitions and active states:

- **`km://schemas/learning-ontologies`**: Retrieves metadata and schemas for all active global Learning Ontologies (canonical graphs only), configured in `.km/config.json`.
- **`km://case/active-graph`**: Returns the complete serialized RDF model of the current Git branch's named graph (runtime). Git diffs use `case-exports/graphs/{ref}.ttl`.
- **`km://case/active-exceptions`**: Lists all active local exceptions (both pending and approved) registered for the current workspace.
- **`km://learning-ontologies/{ontology-id}/canonical`**: Returns the serialized canonical graph for a specific Learning Ontology.
- **`km://learning-ontologies/{ontology-id}/governance`**: Returns MR governance records from **source** LO store (curator review).
- **`km://mr/{ontology-id}/{mr-id}`**: Returns derived MR review document.

## Implementation

The system is implemented in Python utilizing a **relaxed hexagonal architecture**, prioritizing real-world runtime performance and latency considerations over strict academic separation of concerns.

### Core Technology Stack

- **`pyoxigraph`**: Serves as the high-performance RDF graph database for quad-store and named-graph management.
- **`pydantic`**: Enforces robust data validation, type safety, and schema configurations.
- **`pyshacl`**: Executes comprehensive validation of semantic graph integrity against SHACL shapes.
- **`rdflib`**: Handles standard RDF parsing, translation, and serialization.

