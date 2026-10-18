# TruthBranch — Essential Cypher Queries & Traversal Guide

This document catalogs the Cypher queries that power **TruthBranch**'s graph-native impact analysis, governance validation checks, branch diffing, and atomic merge operations on **FalkorDB**.

---

## 1. Multi-Hop Impact Analysis & Lineage

When a fact changes (e.g., `pricing.pro.monthly@v1` is updated), TruthBranch traverses four distinct topological paths in FalkorDB to discover the complete blast radius:

### 1.1. Direct Document Citers
Finds documents that directly cite the target fact via `:CITES`.
```cypher
MATCH (d:Document)-[:CITES]->(f:Fact {id: $old_fact_id})
RETURN d.id AS doc_id, d.title AS title, d.status AS status
```
* **Execution:** Direct index lookup on `f.id` followed by single-hop incoming edge traversal.
* **Matches in Scenario A:** `doc:pricing_page`, `doc:sales_deck`, `doc:faq`, `doc:revenue_forecast_q4`.

---

### 1.2. Downstream Derived Facts
Finds facts that mathematically or logically derive from the changed fact across 1 to 3 hops via `:DERIVED_FROM`.
```cypher
MATCH (g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id: $old_fact_id})
RETURN DISTINCT g.id AS fact_id, g.key AS key
```
* **Execution:** FalkorDB matrix multiplication along the `:DERIVED_FROM` edge type.
* **Matches in Scenario A:** `fact:pricing.pro.annual@v1` (via `rule: "x10"`).

---

### 1.3. Documents Citing Downstream Facts
Finds documents that do not cite the monthly price directly, but cite a fact derived from it (such as the annual price).
```cypher
MATCH (d:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id: $old_fact_id})
RETURN DISTINCT d.id AS doc_id, g.id AS via_fact
```
* **Matches in Scenario A:** `doc:pricing_page` (cites annual price).

---

### 1.4. Multi-Hop Derived Documents (Content Cascades)
Finds documents that derive from direct citers through up to 3 hops of `:DERIVED_FROM` document chains.
```cypher
MATCH (d1:Document)-[:CITES]->(f:Fact {id: $old_fact_id})
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1)
RETURN DISTINCT d2.id AS doc_id, d1.id AS via_doc
```
* **Matches in Scenario A:**
  - `doc:support_macro_upgrade` (derived from `doc:faq`)
  - `doc:investor_update` (derived from `doc:revenue_forecast_q4`)
  - `doc:board_deck` (derived from `doc:investor_update`, 2 hops away from direct citer)

---

### 1.5. Documents Derived from Downstream Citers
Finds documents derived from documents that cite downstream derived facts.
```cypher
MATCH (d1:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id: $old_fact_id})
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1)
RETURN DISTINCT d2.id AS doc_id, d1.id AS via_doc, g.id AS via_fact
```

---

### 1.6. Explainable Shortest Path ("Why" Path)
Computes the exact provenance path justifying why a document is impacted, displayed in the Admin Console.
```cypher
MATCH p = (d2:Document {id: $doc_id})-[:DERIVED_FROM*0..3]->(d1:Document)-[:CITES]->(f:Fact {id: $old_fact_id})
RETURN [n IN nodes(p) | n.id] AS path
ORDER BY length(p) ASC
LIMIT 1
```
* **Example Output for Board Deck:**
  `["doc:board_deck", "doc:investor_update", "doc:revenue_forecast_q4", "fact:pricing.pro.monthly@v1"]` (Length 4 nodes).

---

### 1.7. Document Metadata Batch Enrichment
Enriches discovered documents with their responsible owners and target publishing systems in a single round-trip.
```cypher
MATCH (d:Document) WHERE d.id IN $doc_ids
OPTIONAL MATCH (d)-[:OWNED_BY]->(p:Person)
OPTIONAL MATCH (d)-[:PUBLISHED_IN]->(s:System)
RETURN d.id AS doc_id, d.title AS title, d.status AS status, d.content AS content,
       p.id AS owner_id, p.name AS owner_name,
       s.id AS system_id, s.name AS system_name
```

---

## 2. Automated Governance & Validation Checks

Before any Change Request can transition to `CHECKS_PASSED` or `READY_FOR_REVIEW`, automated governance rules run against the candidate branch.

### 2.1. Source Validation Check (`SOURCE_INVALID`)
Verifies that the evidence justifying the change exists, has `valid: true`, and meets minimum trust requirements.
```cypher
MATCH (s:Source {id: $source_id})
RETURN s.valid AS valid, s.trust AS trust, s.title AS title
```
* **Behavior in Scenario B:** Fails when source is `src:slack_rumor_2026_10` (`valid: false`, `trust: 0.20`), preventing unverified changes from reaching human reviewers.

---

### 2.2. Regional Contradiction Check (`CONTRADICTION`)
Finds active facts in the graph that share the exact same `subject` and `attribute` but carry a different namespace key or value without explicit scoping.
```cypher
MATCH (f:Fact {key: $key, status: 'ACTIVE'})
MATCH (c:Fact {subject: f.subject, attribute: f.attribute, status: 'ACTIVE'})
WHERE c.key <> f.key
RETURN c.id AS conflicting_id, c.key AS conflicting_key, c.value AS conflicting_value
```
* **Behavior in Scenario C:** Detects `fact:pricing.pro.monthly.eu@v1` ($45) when modifying US monthly pricing, flagging a regional contradiction.

---

### 2.3. Unaddressed Impact Check (`UNADDRESSED_IMPACT`)
Queries the branch to ensure that every document in the computed impact set has either been edited or marked `NEEDS_REVIEW`.
```cypher
MATCH (e:ProposedEdit)-[:EDITS]->(d:Document)
RETURN DISTINCT d.id AS edited_doc_id
```
```cypher
MATCH (d:Document {status: 'NEEDS_REVIEW'})
RETURN DISTINCT d.id AS stale_doc_id
```
* **Condition:** `unaddressed = impact_set - (edited_docs | stale_docs)`. If `unaddressed` is non-empty, the check fails with rule `UNADDRESSED_IMPACT`.

---

### 2.4. Literal Value Leak Check (`LITERAL_VALUE_LEAK`)
Scans all documents in the graph that do **not** have formal `:CITES` edges to detect un-governed mentions of the old value.
```cypher
MATCH (d:Document)
RETURN d.id, d.title, d.content
```
* **Regex Engine:** Matches isolated `$49` (with negative lookahead and lookbehind to prevent false-positives on `$149` or `49 engineers`).
* **Result in Lumen Dataset:** Flags `doc:partner_faq` as an unlinked shadow dependency.

---

## 3. Branch Diffing & Version Comparison

### 3.1. Changed Facts on Branch
Finds all facts on the candidate branch that have been updated to a new version.
```cypher
MATCH (f:Fact {status: 'ACTIVE'})
WHERE f.version > 1
RETURN f.id AS id, f.key AS key, f.version AS version, f.value AS value, f.unit AS unit
```

---

## 4. Atomic Merge & Re-Pointing Operations

Upon human approval, validated mutations from the branch are committed onto `kb_main` in an atomic pipeline:

### 4.1. Superseding the Old Fact & Inserting the New Version
```cypher
MATCH (old:Fact {key: $key, status: 'ACTIVE'})
SET old.status = 'SUPERSEDED'
CREATE (new:Fact {
    id: $new_id,
    key: $key,
    version: $new_version,
    subject: old.subject,
    attribute: old.attribute,
    value: $new_value,
    unit: old.unit,
    status: 'ACTIVE',
    created_at: $timestamp
})
CREATE (new)-[:SUPERSEDES]->(old)
```

---

### 4.2. Preserving Provenance & Ownership
```cypher
MATCH (old:Fact {id: $old_id})-[:OWNED_BY]->(p:Person), (new:Fact {id: $new_id})
MERGE (new)-[:OWNED_BY]->(p)
```
```cypher
MATCH (f:Fact {id: $fact_id}), (s:Source {id: $source_id})
MERGE (f)-[:SOURCED_FROM]->(s)
```

---

### 4.3. Dynamic Downstream Fact Recalculation
Recalculates downstream derived facts (e.g. Annual = Monthly × 10) and maintains lineage.
```cypher
MATCH (new_derived:Fact {id: $derived_id})
MATCH (new_base:Fact {key: $base_key, status: 'ACTIVE'})
MERGE (new_derived)-[:DERIVED_FROM {rule: 'x10'}]->(new_base)
```

---

### 4.4. Re-pointing Incoming Citations
Re-points all existing `:CITES` edges from the superseded fact version to the newly active fact version.
```cypher
MATCH (d:Document {id: $doc_id})-[c:CITES]->(old:Fact {id: $old_id})
MATCH (new:Fact {id: $new_id})
DELETE c
MERGE (d)-[:CITES]->(new)
```

---

### 4.5. Applying Text Edits & Marking Stale Docs
Updates content for documents with approved proposed edits:
```cypher
MATCH (d:Document {id: $doc_id})
SET d.content = $new_content, d.last_reviewed = $reviewed_date
```
Flags unedited downstream derived documents for human attention:
```cypher
MATCH (d:Document {id: $doc_id})
SET d.status = 'NEEDS_REVIEW'
```

---

### 4.6. Incrementing Production Graph Revision
Ensures optimistic concurrency tracking across all readers and branches:
```cypher
MATCH (m:Meta {id: 'main'})
SET m.revision = m.revision + 1
```

---

## 5. Why FalkorDB for Graph Traversal?

| Requirement | Traditional RDBMS / Document Store | FalkorDB (TruthBranch) |
| :--- | :--- | :--- |
| **Multi-Hop Traversal** | Recursive SQL CTEs with high join overhead | Native GraphBLAS sparse matrix multiplications (< 2 ms) |
| **Branch Isolation** | Expensive table cloning or logical row tagging | Sub-10ms physical graph duplication (`GRAPH.COPY`) |
| **Lineage Proofs** | Impractical without custom graph indexing | Built-in path extraction (`nodes(p)`) in a single query |
| **Audit & Versioning** | Complex temporal tables | Graph-native `:SUPERSEDES` and `:CITES` re-pointing |
