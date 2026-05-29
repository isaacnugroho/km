## Brief

The **Knowledge Management MCP** is a neuro-symbolic bridge designed to capture the "How" (processes, rationale, exceptions) and the "What" of problem analysis and design. It operates on a version-controlled semantic hyper-graph utilizing a dual-ontology design, with validation and integrity constraints enforced via **SHACL (Shapes Constraint Language)**:

1. **The Learning Ontologies:** Ontology of ontologies to capture the "How" of knowledge domains.
2. **The Case Ontologies:** Local, dynamic, and situational realities derived from problem analysis and design.

KM is MCP tool for managing agent knowledge/memory to prevent hallucination and provide clearer context

### The Learning Ontologies

Learning ontologies are collection of knowledge organized or categorized by domain. Each learning ontology:
- Stored in a directory
- A README.md file in the directory that describes the purpose of the ontology
- Should be self contained with all neccessary classes and relationship and can be used independently

Adding knowledge to the learning ontology involves the following steps:
1. Identify new concepts and relationship
2. Create merge request with diff to add the new concepts and relationship to the ontology
3. Human to approve the merge request
4. The ontology is updated with the new concepts and relationship only after the merge request is approved

> [!NOTE]
> **Domain-Specific Merge Requests:** A "Merge Request" (MR) within the KM system is an *internal, semantic-level concept* rather than a Git/GitHub/GitLab hosting platform PR/MR. While it conceptually mirrors the propose-review-approve-merge lifecycle, it is executed and tracked entirely within the KM system's hyper-graph itself.

### The Case Ontology

Case ontologies:
- Located in the workspace/working directory
- Has ontology of learning ontologies being used in the workspace, configured by a config file
- Has knowledge related to the current problem/case being solved, including the facts, concepts, relationship, rules and process being applied
- Each "how" knowledge i.e. the "how" part of the solution should be linked to the related learning ontologies knowledge
- It is allowed to add exception for not following a learning ontology knowledge, with proper documentation and rationale
- Constructed as quad-store to allow named graph according to the repository branch

Human can initiate promoting knowledge from the case ontology to learning ontologies which will be handled as a merge request to the learning ontology

### Knowledge Lifecycle & Evolution

Human can review the learning ontology periodically and decide to refactor, update, deprecate or archive any part of the ontology. This action should be performed through merge request.

### Governance & Human-in-the-Loop

Who owns, validates, and authors the semantic graph?
- **Case Fact Ingestion:** The agent dynamically discovers and registers facts during runtime.
- **Exception Authority:** The agent can self-declare local exceptions, but all exceptions require explicit human authorization before execution.
- **Curation Boundaries:** Individual developer maintains the Learning Ontologies.

### Version Control & State Synchronization

The Case Ontology is not synchronized with the source code repository. The Case Ontology is specific to a workspace and is not version controlled in the same way as the source code repository.

- **Branch Switch Detection:** watch `.git/HEAD`
- **Branch Inheritance & Fallback Logic:** The case ontology is cloned from the parent branch when a new branch is created.
- **Workspace Portability & Porting:** Human should manualy copy/backup and restore the case ontology.
- **Branch Merging Logic:** The system monitors Git state changes (via `.git/refs/` and `.git/HEAD`). When a branch (e.g. `feature-a`) is detected as merged into the active branch (either locally or via a pulled remote merge), the system does not merge automatically. Instead, it flags a warning to the developer, allowing them to explicitly decide whether to merge the branch's Case Ontology graph into the active branch graph or ignore and delete it.

### Conflict Resolution & Validation

How are logical contradictions and rule violations managed?
- **Cross-Ontology Contradictions:** Human should review and resolve contradictions. The system should flag these contradictions to the human for review.
- **Constraint Enforcement (SHACL):** The system acts as a hard "linter" powered by **SHACL (Shapes Constraint Language)** shapes, validating graph states and halting agent execution on un-excepted constraint violations.
