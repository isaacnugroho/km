# Brief

The **Knowledge Management MCP** is a neuro-symbolic bridge designed to capture the "How" (processes, rationale, exceptions) and the "What" of problem analysis and design. It operates on a version-controlled semantic hyper-graph utilizing a dual-ontology design, with validation and integrity constraints enforced via **SHACL (Shapes Constraint Language)**:

1. **The Learning Ontologies:** Ontology of ontologies to capture the "How" of knowledge domains.
2. **The Case Ontologies:** Local, dynamic, and situational realities derived from problem analysis and design.

KM is MCP tool for managing agent knowledge/memory to prevent hallucination and provide clearer context

## The Learning Ontologies

Learning ontologies are collection of knowledge organized or categorized by domain. Each learning ontology:
- Stored in a directory
- A README.md file in the directory that describes the purpose of the ontology
- Should be self contained with all neccessary classes and relationship and can be used independently

Adding knowledge to the learning ontology involves the following steps:
1. Identify new concepts and relationships.
2. Create a merge request with a semantic diff to add the new concepts and relationships to the ontology.
3. Human reviews and approves the merge request.
4. The ontology is updated with the new concepts and relationships only after the merge request is approved.

> [!NOTE]
> **Domain-Specific Merge Requests:** A "Merge Request" (MR) within the KM system is an *internal, semantic-level concept* rather than a Git/GitHub/GitLab hosting platform PR/MR. While it conceptually mirrors the propose-review-approve-merge lifecycle, it is executed and tracked entirely within the KM system's hyper-graph itself.
> 
> *   **Document Structure:** Each Merge Request is represented as a structured semantic document containing two key sections:
>     1.  **Summary of Changes:** A human-readable section outlining the metadata (including the **exact approval command** to run, target ontology, author, and date), engineering rationale, targeted concepts, and high-level structural impact.
>     2.  **Detailed Changes:** The exact technical diff specifying the RDF `diff_insertions` and `diff_deletions` in Turtle serialization.
> *   **Human Approval Interface:** The approval is finalized by the human developer issuing the explicit command/prompt:
>     ```
>     approve <doc name>
>     ```
>     *(e.g., `approve km://mr/react-conventions/mr-402` or `approve docs/mrs/add-high-frequency-throttle-shape.md`)*

## The Case Ontology

Case ontologies:
- Located in the workspace/working directory
- Has ontology of learning ontologies being used in the workspace, configured by a config file
- Has knowledge related to the current problem/case being solved, including the facts, concepts, relationship, rules and process being applied
- Each "how" knowledge i.e. the "how" part of the solution should be linked to the related learning ontologies knowledge
- It is allowed to add exception for not following a learning ontology knowledge, with proper documentation and rationale
- Constructed as quad-store to allow named graph according to the repository branch

Human can initiate promoting knowledge from the case ontology to learning ontologies which will be handled as a merge request to the learning ontology

## Knowledge Lifecycle & Evolution

Human can review the learning ontology periodically and decide to refactor, update, deprecate or archive any part of the ontology. This action should be performed through merge request.

## Governance & Human-in-the-Loop

Who owns, validates, and authors the semantic graph?
- **Case Fact Ingestion:** The agent dynamically discovers and registers facts during runtime.
- **Exception Authority:** The agent can self-declare local exceptions, but all exceptions require explicit human authorization before execution.
- **Curation Boundaries:** Individual developer maintains the Learning Ontologies.

## Version Control & State Synchronization

The Case Ontology is not synchronized with the source code repository. The Case Ontology is specific to a workspace and is not version controlled in the same way as the source code repository.

- **Branch Switch Detection:** watch `.git/HEAD`
- **Branch Inheritance & Fallback Logic:** The case ontology is cloned from the parent branch when a new branch is created.
- **Workspace Portability & Porting:** Human should manualy copy/backup and restore the case ontology.
- **Branch Merging Logic:** The system monitors Git state changes (via `.git/refs/` and `.git/HEAD`). When a branch (e.g. `feature-a`) is detected as merged into the active branch (either locally or via a pulled remote merge), the system does not merge automatically. Instead, it flags a warning to the developer, allowing them to explicitly decide whether to merge the branch's Case Ontology graph into the active branch graph or ignore and delete it.

## Conflict Resolution & Validation

How are logical contradictions and rule violations managed?
- **Cross-Ontology Contradictions:** Human should review and resolve contradictions. The system should flag these contradictions to the human for review.
- **Constraint Enforcement (SHACL):** The system acts as a hard "linter" powered by **SHACL (Shapes Constraint Language)** shapes, validating graph states and halting agent execution on un-excepted constraint violations.

## MCP Server Interface

The KM MCP Server exposes a standard set of Tools and Resources to the host agent, enabling seamless reading, writing, validation, and human-in-the-loop control of the semantic graph.

### 1. MCP Tools

| Tool Name                 | Parameters                                                                                           | Returns                                                                                      | Description                                                                                                                                                                                  |
| :------------------------ | :--------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ingest_case_facts`       | `facts` (JSON-LD or Turtle string), `format` (string)                                                | `{ "status": "success", "triples_added": int }`                                              | Ingests new contextual facts, concepts, and relationships from the active case into the named graph mapped to the active branch.                                                             |
| `validate_constraints`    | *None*                                                                                               | `{ "conforms": bool, "violations": [Violation] }`                                            | Runs SHACL validation on the active named graph against shapes imported from configured Learning Ontologies. Halts execution if violations are found and no approved local exception exists. |
| `propose_local_exception` | `bypasses_shape` (URI), `target_node` (URI), `rationale` (string)                                    | `{ "exception_id": URI, "status": "PENDING_APPROVAL" }`                                      | Declares a local exception to bypass a specific SHACL shape for a given focus node. Returns details so the agent can prompt the human developer.                                             |
| `approve_local_exception` | `exception_id` (URI), `approver` (string), `signature` (string)                                      | `{ "status": "APPROVED", "timestamp": string }`                                              | Records human approval signature and timestamp, enabling the SHACL linter to bypass the specified shape constraint.                                                                          |
| `query_semantic_graph`    | `query` (SPARQL query string)                                                                        | SPARQL Select/Ask Result (JSON)                                                              | Executes a read-only SPARQL query over the merged active Case named graph and all imported global Learning Ontologies.                                                                       |
| `propose_semantic_mr`     | `target_ontology` (URI), `rationale` (string), `diff_insertions` (Turtle), `diff_deletions` (Turtle) | `{ "mr_id": URI, "status": "PENDING" }`                                                      | Initiates the promotion of locally discovered patterns or exceptions by creating a semantic Merge Request in the system's meta-graph.                                                        |
| `get_system_status`       | *None*                                                                                               | `{ "active_branch": string, "learning_ontologies": [URI], "pending_exceptions_count": int }` | Returns runtime environmental state, loaded ontologies, and active pending exceptions.                                                                                                       |

### 2. MCP Resources

The server exposes read-only structural data to the host agent to clarify schema definitions and active states:

- **`km://schemas/learning-ontologies`**: Retrieves metadata and schemas for all active global Learning Ontologies configured in `.km/config.json`.
- **`km://case/active-graph`**: Returns the complete serialized RDF model of the current Git branch's named graph.
- **`km://case/active-exceptions`**: Lists all active local exceptions (both pending and approved) registered for the current workspace.

## Implementation

The system is implemented in Python utilizing a **relaxed hexagonal architecture**, prioritizing real-world runtime performance and latency considerations over strict academic separation of concerns.

### Core Technology Stack

- **`pyoxigraph`**: Serves as the high-performance RDF graph database for quad-store and named-graph management.
- **`pydantic`**: Enforces robust data validation, type safety, and schema configurations.
- **`pyshacl`**: Executes comprehensive validation of semantic graph integrity against SHACL shapes.
- **`rdflib`**: Handles standard RDF parsing, translation, and serialization.

