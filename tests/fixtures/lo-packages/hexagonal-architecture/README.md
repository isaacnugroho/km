# Hexagonal Architecture Learning Ontology

**Domain:** Ports and Adapters (hexagonal) architecture — application core, boundary ports, and infrastructure adapters.

**Purpose:** Tag case components with hexagonal roles and validate dependency direction: adapters talk to ports; the core defines, realizes, and uses ports but never depends on adapters directly.

**Ontology IRI:** `http://architecture.org/hexagonal`  
**Prefix:** `hex:` → `http://architecture.org/hexagonal#`

---

## Package layout

```
hexagonal-architecture/
├── README.md              # This file
├── config.json            # LO package config (ontology_id, prefix, named graphs)
├── lo_quads.db            # Runtime quad-store (Git ignored)
└── exports/
    ├── main.ttl           # Canonical vocabulary + SHACL shapes (Git authority)
    └── governance/        # One Turtle file per semantic MR (Git authority)
```

Git authority is `exports/main.ttl` and `exports/governance/*.ttl`. The MCP daemon materializes a workspace cache at `.km/lo-cache/hexagonal-architecture/` on startup.

---

## Bind to a workspace

Add a learning-ontology binding in `.km/config.json`. Use an absolute path or a path relative to the application workspace root.

**Read-only** (typical for application repos):

```json
{
  "ontology_id": "hexagonal-architecture",
  "source": "../ontologies/hexagonal-architecture",
  "mode": "read_only"
}
```

**Curator** (required to propose or approve semantic MRs against this LO):

```json
{
  "ontology_id": "hexagonal-architecture",
  "source": "../ontologies/hexagonal-architecture",
  "mode": "curator"
}
```

The `ontology_id` must match `config.json` in this package.

---

## Vocabulary summary

| Class                 | Role                              |
| :-------------------- | :-------------------------------- |
| `hex:ApplicationCore` | Business logic inside the hexagon |
| `hex:DrivingPort`     | Inbound API / use-case contract   |
| `hex:DrivenPort`      | Outbound SPI the core requires    |
| `hex:DrivingAdapter`  | Inbound translator (REST, CLI, …) |
| `hex:DrivenAdapter`   | Outbound translator (DB, mail, …) |

| Property         | Domain → Range               | Meaning                        |
| :--------------- | :--------------------------- | :----------------------------- |
| `hex:defines`    | Core → Port                  | Core owns the port             |
| `hex:realizes`   | Core → DrivingPort           | Core implements inbound port   |
| `hex:uses`       | Core → DrivenPort            | Core depends on outbound port  |
| `hex:invokes`    | DrivingAdapter → DrivingPort | Adapter calls inbound port     |
| `hex:implements` | DrivenAdapter → DrivenPort   | Adapter fulfills outbound port |

---

## Case fact example

Register components in the active case graph (branch-scoped). Replace `case:` with your workspace case namespace.

```turtle
@prefix case: <http://km.local/cases/my-app/> .
@prefix hex:  <http://architecture.org/hexagonal#> .

case:order-service a hex:ApplicationCore ;
    hex:defines case:place-order-port , case:order-repository-port ;
    hex:realizes case:place-order-port ;
    hex:uses case:order-repository-port .

case:place-order-port a hex:DrivingPort .
case:order-repository-port a hex:DrivenPort .

case:order-rest-controller a hex:DrivingAdapter ;
    hex:invokes case:place-order-port .

case:postgres-order-repo a hex:DrivenAdapter ;
    hex:implements case:order-repository-port .
```

After ingestion, run `validate_constraints` — the MCP SHACL linter checks case facts against shapes in this LO's canonical graph.

---

## SHACL shapes

| Shape                                  | Enforces                                   |
| :------------------------------------- | :----------------------------------------- |
| `hex:DrivingAdapterInvocationShape`    | Driving adapters invoke a driving port     |
| `hex:DrivenAdapterImplementationShape` | Driven adapters implement a driven port    |
| `hex:PortOwnershipShape`               | Every port is defined by a core            |
| `hex:CoreRealizesDrivingPortShape`     | Core realizes each driving port it defines |
| `hex:CoreUsesDrivenPortShape`          | Core uses each driven port it defines      |
| `hex:CoreAdapterIsolationShape`        | Core has no direct dependency on adapters  |

Violations halt agent execution unless an approved local exception exists in the case graph (see KM spec §6).

---

## Governance

Changes to this ontology follow the semantic MR workflow:

1. `propose_semantic_mr` with Turtle diffs (requires `mode: "curator"` on the binding).
2. Human review via derived document at `.km/mrs/`.
3. `approve_semantic_mr` merges into the source canonical graph and regenerates `exports/main.ttl`.

Pending MR proposal graphs never participate in agent validation.
