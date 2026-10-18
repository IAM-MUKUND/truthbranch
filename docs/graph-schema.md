# TruthBranch — Graph Data Model & Schema Specification

TruthBranch structures enterprise knowledge as an authoritative, versioned Property Graph stored in **FalkorDB**. This document defines the canonical schema, node labels, relationship types, property constraints, and indexing architecture.

---

## 1. Schema Overview

The graph models company ground truth at two levels:
1. **Atomic Facts (`Fact`):** Granular, versioned claims of truth (e.g. pricing, policy numbers, SLAs).
2. **Knowledge Assets (`Document`):** Human-facing and system documents (e.g. pricing pages, pitch decks, FAQs, financial forecasts) that cite or derive from facts.
3. **Provenance & Governance (`Source`, `Person`, `System`):** Supporting evidentiary sources, organizational owners, and publishing destinations.

```
       [Source] (src:*)
          │
          │ :SOURCED_FROM
          ▼
       [Fact] (fact:*@v1) ───────────[:OWNED_BY]───────────► [Person] (p:*)
          │         ▲                                           ▲
          │         │ :DERIVED_FROM (e.g. rule: "x10")         │
:CITES    │         │                                           │ :OWNED_BY
          ▼         │                                           │
      [Document] (doc:*) ───────────────────────────────────────┘
          │         ▲
          │         │ :DERIVED_FROM
          │         │
          ▼         │
   [Document] (doc:*) ───────────[:PUBLISHED_IN]───────────► [System] (sys:*)
```

---

## 2. Node Types & Property Schemas

### 2.1. `Fact`
An immutable, versioned unit of organizational truth. Facts are identified by a composite ID containing their hierarchical key and revision number (e.g., `fact:pricing.pro.monthly@v1`).

| Property | Type | Description | Example / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | **Primary Key**. Format: `fact:<key>@v<version>` | `fact:pricing.pro.monthly@v1` |
| `key` | `STRING` | Dot-notation namespace of the fact | `pricing.pro.monthly` |
| `version` | `INTEGER` | Monotonically increasing revision number | `1`, `2` |
| `subject` | `STRING` | Entity or domain the fact pertains to | `pro_plan`, `support` |
| `attribute` | `STRING` | Specific property or metric | `monthly_price`, `refund_window_days` |
| `value` | `ANY` | Ground truth value (numeric or string) | `49`, `59`, `30` |
| `unit` | `STRING` | Unit of measure or currency | `USD`, `days` |
| `status` | `STRING` | Lifecycle state | `'ACTIVE'` or `'SUPERSEDED'` |
| `created_at`| `STRING` | ISO 8601 creation timestamp | `2025-01-15T00:00:00Z` |

---

### 2.2. `Document`
A content artifact consumed by internal teams or public customers.

| Property | Type | Description | Example / Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | **Primary Key**. Format: `doc:<slug>` | `doc:pricing_page`, `doc:board_deck` |
| `title` | `STRING` | Human-readable document name | `"Pricing page"`, `"Board deck"` |
| `kind` | `STRING` | Document category | `'page'`, `'deck'`, `'faq'`, `'forecast'`, `'macro'` |
| `status` | `STRING` | Governance status | `'CURRENT'` or `'NEEDS_REVIEW'` |
| `last_reviewed` | `STRING` | Date string (YYYY-MM-DD) | `2026-09-01` |
| `content` | `STRING` | Raw textual content containing assertions | `"Lumen Pro costs $49 per month..."` |

---

### 2.3. `Person`
An organizational stakeholder who owns facts, documents, or approves change requests.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | **Primary Key**. Format: `p:<name>` | `p:maya`, `p:arjun` |
| `name` | `STRING` | Full name | `"Maya Rao"`, `"Arjun Mehta"` |
| `role` | `STRING` | Organizational title | `"Product owner"`, `"Finance owner"` |
| `email` | `STRING` | Corporate email address | `maya@lumen.example` |

---

### 2.4. `Source`
Evidence or legal justification verifying a fact.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | **Primary Key**. Format: `src:<slug>` | `src:pricing_committee_memo_2026_10` |
| `title` | `STRING` | Title or description of the evidence | `"Pricing committee memo, Oct 2026"` |
| `kind` | `STRING` | Medium of evidence | `'announcement'`, `'memo'`, `'chat'`, `'web'` |
| `valid` | `BOOLEAN`| Whether the source is legally authoritative | `true`, `false` |
| `trust` | `FLOAT` | Trust score between 0.0 and 1.0 | `0.95` (memo), `0.20` (Slack rumor) |

---

### 2.5. `System`
The external publishing system or tool where a document is hosted.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | **Primary Key**. Format: `sys:<slug>` | `sys:website_cms`, `sys:crm`, `sys:finance_sheet` |
| `name` | `STRING` | Human-readable system name | `"Website CMS"`, `"Helpdesk"`, `"CRM"` |

---

### 2.6. `Meta` (Per Graph)
Tracks the authoritative revision of the graph.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `STRING` | Identifier | `'main'` |
| `revision` | `INTEGER` | Monotonically increasing graph revision | `1`, `2`, `3` |

---

## 3. Relationship Types

| Relationship | Start Node | End Node | Properties | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `:CITES` | `Document` | `Fact` | None | Direct citation: Document explicitly states or relies upon the value of this Fact. |
| `:DERIVED_FROM` | `Fact` | `Fact` | `rule: STRING` | Mathematical or logical derivation (e.g., `rule: "x10"` for annual pricing). |
| `:DERIVED_FROM` | `Document` | `Document` | None | Content cascade: Downstream document derives metrics or conclusions from upstream document. |
| `:SOURCED_FROM` | `Fact` | `Source` | None | Evidentiary backing for the fact. |
| `:OWNED_BY` | `Fact` \| `Document` | `Person` | None | Directly accountable owner responsible for reviewing changes. |
| `:PUBLISHED_IN`| `Document` | `System` | None | Integration endpoint where document is rendered. |
| `:SUPERSEDES` | `Fact` | `Fact` | None | Immutable lineage: Version N+1 supersedes Version N upon merge. |
| `:EDITS` *(Branch only)* | `ProposedEdit` | `Document` | None | Ephemeral candidate edit generated by the autonomous agent on a branch. |

---

## 4. Database Indexes & Performance

To guarantee sub-millisecond query execution in FalkorDB, attribute indexes are created during initialization:

```cypher
CREATE INDEX FOR (f:Fact) ON (f.id);
CREATE INDEX FOR (f:Fact) ON (f.key);
CREATE INDEX FOR (f:Fact) ON (f.status);
CREATE INDEX FOR (d:Document) ON (d.id);
CREATE INDEX FOR (p:Person) ON (p.id);
CREATE INDEX FOR (s:Source) ON (s.id);
CREATE INDEX FOR (s:System) ON (s.id);
```

When a branch is created via `GRAPH.COPY kb_main kb_cr_<id>`, FalkorDB clones both the adjacency matrices and the attribute index structures into the new container in **under 10 milliseconds**.

---

## 5. Architectural Invariants

1. **Acyclicity:** Document and fact derivation graphs (`:DERIVED_FROM*`) must be strictly Directed Acyclic Graphs (DAGs). Circular dependencies are rejected.
2. **Single Active Version:** In `kb_main`, for any fact key (e.g. `pricing.pro.monthly`), there exists **exactly one** Fact node with `status: 'ACTIVE'`.
3. **Immutable History:** When a fact is updated from `v1` to `v2`, `v1` is never deleted or overwritten in place. Instead, `v1.status` is transitioned to `'SUPERSEDED'`, `v2` is inserted with `status: 'ACTIVE'`, and a `:SUPERSEDES` relationship is created: `(v2)-[:SUPERSEDES]->(v1)`.
