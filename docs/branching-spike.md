# TruthBranch — Branching Spike Report (Block 1.4)

**Date:** 2026-10-16  
**Environment:** Linux / WSL2  
**Client Version:** `falkordb 1.8.0` (Python)  
**Database Image:** `falkordb/falkordb:latest` (Docker, mapped port `6380:6379`)  
**Decision:** **OPTION A (Physical Graph Copy via `GRAPH.COPY`) LOCKED IN**

---

## 1. Executive Summary

The top architectural risk for TruthBranch was whether FalkorDB's `GRAPH.COPY` could provide true, isolated, fast git-like branches without state corruption or leakage into the authoritative knowledge graph (`kb_main`).

The spike was executed via `scripts/branching_spike.py` against a running FalkorDB instance containing the full Lumen Analytics dataset (29 nodes, 41 edges).

All 4 spike criteria passed with zero issues:
- `GRAPH.COPY` completed in **9.84 ms**.
- Mutations on the branch (`CREATE (:Person)`, `SET Fact.value=999`) produced **zero side effects on `kb_main`**.
- Property indexes (`Fact.id`, etc.) were **fully preserved and active on the clone**.
- `branch.delete()` wiped the candidate graph without affecting `kb_main`.

---

## 2. Evidence and Answers to the Four Core Questions

### Q1: Does `kb_main.copy("kb_cr_test")` work from the Python client?
* **Result:** **PASSED**
* **Time:** 9.84 ms
* **Mechanism:** Python `graph.copy(target_name)` invokes the RedisGraph/FalkorDB command `GRAPH.COPY kb_main kb_cr_test`. The clone is available immediately.

### Q2: Does writing to the branch leave `kb_main` unchanged?
* **Result:** **PASSED (Zero leakage)**
* **Evidence:**
  - Initial `kb_main`: 29 nodes, 41 edges.
  - Branch mutated: Added node `(:Person {id:'p:ghost'})` and mutated `fact:pricing.pro.monthly@v1` to `value: 999, status: 'SUPERSEDED'`.
  - Branch post-mutation count: 30 nodes.
  - `kb_main` post-mutation count: **29 nodes, 41 edges** (unchanged).
  - `kb_main` monthly fact query: `value = 49, status = 'ACTIVE'` (completely untouched).

### Q3: Does the branch contain the indexes?
* **Result:** **CONFIRMED CLONED**
* **Evidence:**
  - Attempting to run `CREATE INDEX FOR (f:Fact) ON (f.id)` on the cloned graph raised:
    `Attribute 'id' is already indexed`.
  - FalkorDB deep-clones both the adjacency matrices and the attribute index structures into the new container.

### Q4: Does deleting the branch work and leave `kb_main` intact?
* **Result:** **PASSED**
* **Evidence:**
  - `branch.delete()` successfully removed `kb_cr_test_spike` from `db.list_graphs()`.
  - `kb_main` was verified after deletion and retained all 29 nodes and 41 edges.

---

## 3. Architecture Impact for Sprint 2

With Option A verified:
1. `POST /api/change-requests` will generate branches with:
   ```python
   main_graph = db.select_graph("kb_main")
   branch_graph = main_graph.copy(f"kb_cr_{cr_id}")
   ```
2. Operations (`UPDATE_FACT`, `ATTACH_SOURCE`, `MARK_STALE`, `PROPOSE_EDIT`) will be replayed directly against `kb_cr_{cr_id}`.
3. Metadata (`ChangeRequest`, `AuditEvent`, `AgentStep`) will reside in `kb_meta` to keep branch graphs lightweight and ephemeral.
4. On approval and merge, validated operations will replay onto `kb_main`, followed by `branch_graph.delete()`.
