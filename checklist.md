
# TruthBranch — Grand Checklist (v2)

> **Git for Company Knowledge.** A knowledge change is proposed on a branch, investigated through the graph, validated, drafted into follow-up edits by an agent, approved by a human, and merged with history preserved.

**Builder:** Mukund (solo) · **Stack:** FastAPI + React (Vite) + Groq + FalkorDB · **Tracks:** 1 (Agents That Act on Connected Data) + 3 (Company Brain)
**Deadline:** Sunday, 18 Oct 2026, 11:59 PM IST (**⚠ verify** on the hackathon rules page) · **Personal deadline: submit by 6:00 PM IST on 18 Oct. The last hours are buffer, not working time.**

How to use this file: tick boxes as you go (`- [x]`). Every task has a short **Why**. Items marked **⚠ verify** are things to confirm the first time you touch them. If you fall behind, jump to **Section 14 (Cut List)** instead of improvising.

---

## 0. What changed from v1 (read once)

| #  | Problem in v1                                                                                                                                                                                         | Fix in v2                                                                                                                                                  |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | **Key collision:** the regional fact reused key `pricing.pro.monthly`, so the merge query `MATCH (old:Fact {key:$key, status:'ACTIVE'})` could match two nodes and supersede the wrong one. | Regional fact now has key `pricing.pro.monthly.eu`; same `subject` + `attribute`, so the contradiction check still fires.                            |
| 2  | **Annual fact left dangling:** `annual` was `DERIVED_FROM monthly@v1` but nothing updated it after the change.                                                                              | Annual is now an impacted **fact**: the engine creates `annual@v2 = 590` via a derivation rule stored on the edge.                                 |
| 3  | **CITES edges never moved on merge**, so after merging, documents still cited the SUPERSEDED fact and the stale check would fail forever on `main`.                                           | New op `REPOINT_CITATION`, applied at merge for every document whose edit is approved.                                                                   |
| 4  | **Weak multi-hop story:** `support_macro_upgrade` cited the fact directly, so no traversal was needed.                                                                                        | Support macro now cites nothing (derived from FAQ only). Added `board_deck` for a 3-level chain.                                                         |
| 5  | **No tempting distractor.**                                                                                                                                                                     | Added `careers_page` ("team of 49 engineers") and `$149` Enterprise text inside the sales deck. Literal matching uses a regex, not plain `CONTAINS`. |
| 6  | **Dataset naming:** `cost_forecast_q4` was titled "Q4 revenue forecast".                                                                                                                      | Renamed to `doc:revenue_forecast_q4`.                                                                                                                    |
| 7  | **State machine gap:** `submit_for_approval` existed as an agent tool but had no state or API endpoint.                                                                                       | Added states `CHECKS_PASSED` and `READY_FOR_REVIEW`, plus `POST /submit`.                                                                            |
| 8  | **`STALE_DEPENDENCY` only looked at direct citers**, but derived docs need coverage too.                                                                                                      | Check now runs over the whole impact set; docs with no literal price get `MARK_STALE` (NEEDS_REVIEW), docs with a literal get `PROPOSE_EDIT`.          |
| 9  | **Scenario C had no resolution path.**                                                                                                                                                          | Resolved by a second `UPDATE_FACT` on the regional key.                                                                                                  |
| 10 | Section numbering skipped 2.4; ID `cost_forecast` inconsistencies.                                                                                                                                  | Renumbered; IDs unified.                                                                                                                                   |
| 11 | Dataset was not designed as a demo.                                                                                                                                                                   | New Section 6 (ground truth), 6.8 (baseline comparison), 6.9 (optional `--scale`). Fictional company **Lumen Analytics**.                          |
| 12 | Hackathon claims were stated as fact.                                                                                                                                                                 | Deadline and rules are marked **⚠ verify**.                                                                                                         |

---

## 1. Table of contents

1. Project snapshot
2. FalkorDB crash course
3. How an LLM talks to a graph database
4. Architecture and repository layout
5. Graph data model
6. Demo dataset and ground truth
7. Cypher query catalog
8. Change operations, branching, merge
9. Quality checks
10. The agent
11. API contract
12. Frontend screens
13. Sprints
14. Cut list
15. Testing checklist
16. Demo script
17. README and submission
18. Risks and troubleshooting

---

## 2. Project snapshot

### 2.1 Three layers (never mix)

| Layer                   | Contents                                                                                                                           |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Vision**        | Git for Company Knowledge: branches, diffs, review, merge, blame for facts and documents.                                          |
| **Hackathon MVP** | One pricing change goes through: propose, branch, impact analysis, validation, agent review, human approval, merge.                |
| **Stretch**       | MCP exposure, graph-path visualization, richer AI edit suggestions, concurrent branches, arbitrary ingestion, `--scale` seeding. |

### 2.2 Must ship (MVP)

- [ ] Synthetic company graph in FalkorDB (facts, documents, sources, people, systems)
- [ ] Candidate branch created from `main`
- [ ] Deterministic, versioned change operations
- [ ] Graph-derived impact analysis with a "why was this flagged" path for every item
- [ ] Keyword-vs-graph baseline comparison (cheap, very persuasive)
- [ ] Quality checks (source missing/invalid, stale dependency, contradiction)
- [ ] An agent that chooses and calls graph tools (Track 1 proof)
- [ ] Human approval gate
- [ ] Controlled merge preserving history (`SUPERSEDES`, audit trail)
- [ ] React review screen
- [ ] README, schema doc, Cypher doc, demo video, public repo

### 2.3 Out of scope

General Git semantics, concurrent branches, three-way merges, arbitrary document ingestion, multi-agent systems, multiple use cases.

### 2.4 Decision priority

1. Graph correctness 2. Safe change workflow 3. Real agent behavior 4. Clear review UI 5. Submission polish 6. Stretch

### 2.5 One-sentence pitch

"Companies change a fact in one place and forget the twenty places that repeat it. TruthBranch treats knowledge like code: you propose a change on a branch, the graph shows everything it touches, an agent investigates and drafts the fixes, a human approves, and the merge keeps the full history."

---

## 3. FalkorDB crash course

### 3.1 What it is

- A **graph database** that speaks the **Redis protocol** (default port `6379`).
- Stores **nodes**, **relationships**, and **properties**; queried with **Cypher**.
- It grew out of the team behind RedisGraph after Redis discontinued that module (around 2023); it is not a 2026 project, but LLM training data knows it less well than Neo4j (matters for Section 4). **⚠ verify** history on falkordb.com if you cite it.

### 3.2 Vocabulary

| Word         | Meaning                                | Example                                               |
| ------------ | -------------------------------------- | ----------------------------------------------------- |
| Graph        | Named container; one server holds many | `kb_main`, `kb_cr_ab12cd34`                       |
| Node         | A thing with labels and properties     | `(:Fact {id:'fact:pricing.pro.monthly@v1'})`        |
| Relationship | Directed, typed connection             | `(:Document)-[:CITES]->(:Fact)`                     |
| Cypher       | Query language                         | `MATCH (d:Document)-[:CITES]->(f:Fact) RETURN d.id` |

### 3.3 Cypher cheat sheet

```cypher
CREATE (:Person {id:'p:maya', name:'Maya'})
MATCH (p:Person) RETURN p.id, p.name
MATCH (f:Fact) WHERE f.status = 'ACTIVE' RETURN f.id
MATCH (d:Document)-[:CITES]->(f:Fact {key:'pricing.pro.monthly'}) RETURN d.title
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1:Document) RETURN d2.id, d1.id   // multi-hop
MERGE (p:Person {id:'p:maya'}) SET p.name = 'Maya'                            // idempotent seed
MATCH (f:Fact {id:$id}) OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s:Source) RETURN f.id, s.id
MATCH (d:Document)-[:OWNED_BY]->(p:Person) RETURN p.name, count(d) AS docs
UNWIND $people AS x MERGE (p:Person {id: x.id}) SET p.name = x.name          // bulk seed
```

### 3.4 Python client

```bash
pip install FalkorDB
```

```python
from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
g = db.select_graph("kb_main")           # graph is created on first write
res = g.query("MATCH (f:Fact {id:$id}) RETURN f.id, f.value",
              params={"id": "fact:pricing.pro.monthly@v1"})
for row in res.result_set: print(row)    # list of lists; res.header = column names
g.ro_query("MATCH (n) RETURN count(n)")  # read-only (use for agent and GET endpoints)
branch = g.copy("kb_cr_ab12cd34")        # GRAPH.COPY: full clone
branch.delete()
db.list_graphs()
```

From the FalkorDB docs: `GRAPH.COPY <src> <dest>` clones nodes, relationships, properties, indexes and constraints; later changes to the source do not affect the copy. **⚠ verify** all four on your version (Section 8.3 spike).

### 3.5 First-timer rules

- [ ] **Always use query parameters** (`$id`), never string concatenation. *Why:* injection and quoting bugs.
- [ ] **Return scalars, not nodes**, from queries you serialize. *Why:* nodes are not JSON-friendly and bloat LLM context.
- [ ] **Use `ro_query` for reads** from the agent and GET endpoints.
- [ ] **Index hot lookups:** `CREATE INDEX FOR (f:Fact) ON (f.id)` for `Fact.id`, `Fact.key`, `Document.id`, `Person.id`, `Source.id`. **⚠ verify** syntax.
- [ ] **Test every query by hand first** (FalkorDB Browser or `redis-cli`). *Why:* separates bad Cypher from bad Python.
- [ ] Graphs appear lazily: seed before querying.
- [ ] Keep node counts tiny. Correctness, not performance, is the goal.

### 3.6 Local setup

```bash
docker run --rm -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

`6379` = database; the bundled browser UI is typically on `3000` (**⚠ verify**). Fallback: FalkorDB Cloud (`FALKORDB_HOST/PORT/PASSWORD`).

---

## 4. How an LLM actually talks to a graph database

### 4.1 The core fact

**An LLM never accesses a database.** It reads text and emits text. The loop is:

1. Your backend tells the model what tools exist (names, descriptions, JSON schemas).
2. The model replies "call tool X with arguments Y".
3. **Your code** runs the tool (Cypher through the client).
4. Your code sends the result back as text.
5. The model reasons, then calls another tool or answers.

### 4.2 Three patterns

| Pattern                                                | How                                | Pros                                  | Cons                                     | Use?                                                 |
| ------------------------------------------------------ | ---------------------------------- | ------------------------------------- | ---------------------------------------- | ---------------------------------------------------- |
| **A. Fixed tools, pre-written Cypher**           | LLM picks tool and arguments only  | Reliable, testable, safe, explainable | Less flexible                            | **Yes, the backbone**                          |
| **B. Text-to-Cypher**                            | LLM writes Cypher from your schema | Flexible, impressive                  | Hallucinated labels, dialect gaps, risky | Optional, read-only, guarded                         |
| **C. Ready-made tooling** (GraphRAG, MCP server) | Companion projects                 | Less code                             | Version and learning risk                | Stretch only. **⚠ verify** what is maintained |

### 4.3 Does the LLM need "skills" to know Cypher?

No training needed. Supply **context**: (1) a schema card, (2) 4 to 6 few-shot question-to-Cypher pairs on *your* schema, (3) rules (read-only, `LIMIT`, parameters, only these labels), (4) an error feedback loop (max 2 retries). Because FalkorDB is under-represented in training data, **you** write and test the risky Cypher (Pattern A); the model does what it is good at: deciding, interpreting, drafting.

### 4.4 Guardrails if you add Pattern B (`graph_explore`)

- [ ] `ro_query` only
- [ ] Reject `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `CALL`, `LOAD` (regex, case-insensitive)
- [ ] Force `LIMIT 50`; truncate long fields
- [ ] Run against the **branch**, never `main`
- [ ] Log the Cypher in the agent timeline

### 4.5 Recommended design

Pattern A for the whole workflow. Pattern B as a Day 3 stretch. **Merge and approve are never agent tools.**

### 4.6 Groq specifics

- Groq supports OpenAI-style tool calling: send `tools=[...]`, receive `tool_calls`, execute, append `{"role":"tool",...}`, call again.

- [ ] **Pick the model from console.groq.com/docs/models** (lineup changes). Larger model for the loop; optional small one for text.
- [ ] `pip install groq`; `temperature=0`.
- [ ] Validate every `tool_call.arguments` with Pydantic; return the validation error as the tool result and allow one retry.
- [ ] Cap the loop at **8 iterations**; cap tool results at about **4 KB**.
- [ ] Retry with backoff on 429. Do not discover rate limits during recording.

---

## 5. Architecture and repository layout

```
React (Vite)  ──HTTP/JSON──►  FastAPI  ──►  Services  ──►  FalkorDB
   review UI                   routers      branching.py      kb_main
                                            operations.py     kb_cr_<id> (branches)
                                            impact.py         kb_meta (CRs, audit, steps)
                                            checks.py
                                            agent/ ──► Groq
```

### 5.1 Three graphs

| Graph          | Purpose                                                                                                                            |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `kb_main`    | Authoritative knowledge. Changed only by an approved merge.                                                                        |
| `kb_cr_<id>` | Branch for one change request (`GRAPH.COPY` from `kb_main`).                                                                   |
| `kb_meta`    | Change requests, ops (JSON), approvals, audit events, agent steps. *Why separate:* otherwise every branch copy carries metadata. |

### 5.2 Repository layout

```
truthbranch/
├── README.md  checklist.md  LICENSE  .env.example  docker-compose.yml
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py  config.py  db.py  schema.py  models.py
│       ├── seed/        data.py  seed.py
│       ├── queries/     lineage.py  impact.py  checks.py  merge.py
│       ├── services/    branching.py  operations.py  impact.py  baseline.py
│       │                checks.py  merge.py  audit.py  state_machine.py
│       ├── agent/       tools.py  loop.py  prompts.py  scripted.py
│       └── routers/     change_requests.py  graph.py  admin.py
│   └── tests/           test_ground_truth.py  test_branching.py  test_merge.py ...
├── frontend/            package.json  src/(api.ts, pages/, components/)
├── scripts/             run_scenario_a.py  run_scenario_b.py
└── docs/                architecture.md  graph-schema.md  cypher-queries.md
                         branching-spike.md  sample-run.json
```

Rules:

- [ ] **All Cypher lives in `queries/`** as named constants (you must document it for submission).
- [ ] Routers hold no business logic; services hold no HTTP.
- [ ] Sync FalkorDB client and plain `def` endpoints for the first build.

---

## 6. Graph data model

### 6.1 Node labels

| Label            | Properties                                                                | Notes                                                                                                                                                      |
| ---------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Fact`         | `id, key, version, subject, attribute, value, unit, status, created_at` | `key` = stable identity; `id = fact:<key>@v<N>`. `status` ∈ `ACTIVE, SUPERSEDED, NEEDS_REVIEW`. **Keys must be unique among ACTIVE facts.** |
| `Source`       | `id, title, kind, valid, trust`                                         | `valid` boolean; `trust` 0 to 1.                                                                                                                       |
| `Document`     | `id, title, kind, content, status, last_reviewed`                       | `status` ∈ `CURRENT, NEEDS_REVIEW`.                                                                                                                   |
| `System`       | `id, name`                                                              | Where a doc lives.                                                                                                                                         |
| `Person`       | `id, name, role, email`                                                 | Owners.                                                                                                                                                    |
| `ProposedEdit` | `id, doc_id, before, after, status, author`                             | On the branch; applied on merge.                                                                                                                           |
| `Meta`         | `id='main', revision`                                                   | One node in `kb_main` (optimistic concurrency).                                                                                                          |

`kb_meta`: `ChangeRequest` (`id, title, status, branch_graph, base_revision, ops_json, created_by, created_at, approved_by, merged_at`), `AuditEvent` (`id, cr_id, type, detail, at`), `AgentStep` (`id, cr_id, idx, tool, args_json, result_summary, at`).

### 6.2 Relationships

| Relationship                               | Meaning                                                                 |
| ------------------------------------------ | ----------------------------------------------------------------------- |
| `(Fact)-[:SOURCED_FROM]->(Source)`       | Evidence                                                                |
| `(Fact)-[:SUPERSEDES]->(Fact)`           | New version replaces old                                                |
| `(Fact)-[:DERIVED_FROM {rule}]->(Fact)`  | Computed from another; `rule` e.g. `"x10"` (annual = monthly × 10) |
| `(Fact)-[:OWNED_BY]->(Person)`           | Accountable person                                                      |
| `(Document)-[:CITES]->(Fact)`            | Document states this fact                                               |
| `(Document)-[:DERIVED_FROM]->(Document)` | Built from another document                                             |
| `(Document)-[:PUBLISHED_IN]->(System)`   | Where it lives                                                          |
| `(Document)-[:OWNED_BY]->(Person)`       | Who must update it                                                      |
| `(ProposedEdit)-[:EDITS]->(Document)`    | Draft change                                                            |

### 6.3 ID conventions

- [ ] Fact `fact:<key>@v<N>` · Document `doc:<slug>` · Person `p:<slug>` · Source `src:<slug>` · System `sys:<slug>`
- [ ] Change request `cr_<8 hex>`; branch graph `kb_cr_<8 hex>`
- [ ] IDs never change. New versions get new IDs; old nodes become `SUPERSEDED`, never deleted.

### 6.4 Versioning (the heart of the project)

- A fact change never overwrites: it creates `@v2`, adds `(v2)-[:SUPERSEDES]->(v1)`, marks `v1` `SUPERSEDED`.
- After a change, any document that still `CITES` a `SUPERSEDED` fact is a **stale dependency**. On merge, approved edits **re-point** `CITES` to the new version (`REPOINT_CITATION`), so `main` ends clean.

### 6.5 Indexes at seed time

`Fact.id, Fact.key, Fact.status, Document.id, Person.id, Source.id, System.id` (**⚠ verify** syntax).

---

## 7. Demo dataset and ground truth

**Design principle:** a synthetic dataset is the correct choice. Real company data is private; public datasets have no `CITES/DERIVED_FROM/SUPERSEDES` structure and no known right answer; and ingestion is out of scope. Every item below exists to prove a specific behavior, so you can say "the system found exactly X and nothing else". **Disclose it as synthetic in the README and video.**

Fictional company: **Lumen Analytics**; product: **Lumen Pro**.

### 7.1 People

| id          | name         | role              | email               |
| ----------- | ------------ | ----------------- | ------------------- |
| `p:maya`  | Maya Rao     | Product owner     | maya@lumen.example  |
| `p:arjun` | Arjun Mehta  | Finance owner     | arjun@lumen.example |
| `p:sofia` | Sofia Khan   | Support owner     | sofia@lumen.example |
| `p:ravi`  | Ravi Iyer    | Sales lead        | ravi@lumen.example  |
| `p:lena`  | Lena Fischer | Partnerships lead | lena@lumen.example  |

### 7.2 Systems

`sys:website_cms`, `sys:helpdesk`, `sys:crm`, `sys:finance_sheet`, `sys:partner_portal`

### 7.3 Sources

| id                                     | title                            | valid           | trust |
| -------------------------------------- | -------------------------------- | --------------- | ----- |
| `src:pricing_announcement_2025`      | Pricing announcement 2025        | true            | 0.95  |
| `src:pricing_committee_memo_2026_10` | Pricing committee memo, Oct 2026 | true            | 0.95  |
| `src:slack_rumor_2026_10`            | Unverified Slack message         | **false** | 0.2   |
| `src:regional_page_2024`             | Regional landing page (2024)     | true            | 0.5   |

### 7.4 Facts

All three pricing facts share `subject='pro_plan'`.

| id                                                                          | key                                  | attribute                                | value | unit | status | source             | owner |
| --------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------- | ----- | ---- | ------ | ------------------ | ----- |
| `fact:pricing.pro.monthly@v1`                                             | `pricing.pro.monthly`              | `monthly_price`                        | 49    | USD  | ACTIVE | announcement_2025  | maya  |
| `fact:pricing.pro.annual@v1`                                              | `pricing.pro.annual`               | `annual_price`                         | 490   | USD  | ACTIVE | announcement_2025  | maya  |
| `fact:support.refund_days@v1`                                             | `support.refund_days`              | `refund_window_days`                   | 30    | days | ACTIVE | announcement_2025  | sofia |
| `fact:pricing.pro.monthly.eu@v1` *(only with `--with-contradiction`)* | **`pricing.pro.monthly.eu`** | `monthly_price` (subject `pro_plan`) | 45    | USD  | ACTIVE | regional_page_2024 | ravi  |

Edge: `(annual@v1)-[:DERIVED_FROM {rule:'x10'}]->(monthly@v1)`.
The fourth fact has a **distinct key** (fixes v1 bug) but the **same subject + attribute** as the monthly price, so the contradiction check fires.

### 7.5 Documents (content is literal; edits depend on it)

| id                            | title                           | system         | owner | cites                            | derived from                | content                                                                                                                              |
| ----------------------------- | ------------------------------- | -------------- | ----- | -------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `doc:pricing_page`          | Pricing page                    | website_cms    | maya  | monthly, annual                  | none                        | "Lumen Pro costs $49 per month, or $490 per year (two months free). Cancel anytime."                                                 |
| `doc:sales_deck`            | Sales deck                      | crm            | ravi  | monthly                          | `doc:pricing_page`        | "Slide 7: Lumen Pro at $49/month. Enterprise starts at $149/month with SSO and audit logs."                                          |
| `doc:faq`                   | Customer FAQ                    | website_cms    | sofia | monthly, refund                  | none                        | "How much is Pro? $49 per month. Refunds are available within 30 days of purchase."                                                  |
| `doc:support_macro_upgrade` | Support macro: upgrade question | helpdesk       | sofia | **none**                   | `doc:faq`                 | "Thanks for asking about upgrading. Pro is billed at the monthly list price shown in our FAQ, and you can switch plans at any time." |
| `doc:revenue_forecast_q4`   | Q4 revenue forecast             | finance_sheet  | arjun | monthly                          | none                        | "Q4 forecast assumes 1,200 Pro seats at $49 per month."                                                                              |
| `doc:investor_update`       | Investor update draft           | finance_sheet  | arjun | **none**                   | `doc:revenue_forecast_q4` | "Pro revenue in Q4 is tracking to plan based on the current forecast and list pricing."                                              |
| `doc:board_deck`            | Board deck                      | finance_sheet  | arjun | **none**                   | `doc:investor_update`     | "Appendix B: revenue projections follow the Q4 forecast model."                                                                      |
| `doc:partner_faq`           | Partner FAQ                     | partner_portal | lena  | **none** (dark dependency) | none                        | "Partners can resell Lumen Pro at the public price of $49 per month and keep a 20% margin."                                          |
| `doc:refund_policy`         | Refund policy                   | website_cms    | sofia | refund                           | none                        | "Customers may request a full refund within 30 days of purchase."                                                                    |
| `doc:onboarding_guide`      | Onboarding guide                | website_cms    | maya  | refund                           | none                        | "Within your first 30 days you can request a refund from Settings. Welcome to Lumen!"                                                |
| `doc:careers_page`          | Careers page                    | website_cms    | maya  | **none**                   | none                        | "Join our team of 49 engineers building analytics for everyone."                                                                     |

### 7.6 What each item proves

| Element                                                   | Purpose                                                                                      |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| pricing_page, sales_deck, faq, revenue_forecast           | Direct citation (baseline case)                                                              |
| annual fact                                               | Fact-level propagation (a *fact* is flagged, not only documents)                           |
| support_macro (via faq), investor_update (via forecast)   | Multi-hop that only a graph finds; **no price literal**, so keyword search misses them |
| board_deck                                                | Deepest chain: `board_deck → investor_update → revenue_forecast → monthly@v1`           |
| partner_faq                                               | Dark dependency: graph cannot see it; literal check catches it (WARN). Shows honest limits   |
| `$149` in sales_deck, `careers_page` ("49 engineers") | Near-miss distractors: prove precision                                                       |
| refund_policy, onboarding_guide                           | Unrelated distractors: never flagged                                                         |
| Slack source                                              | Scenario B (agent changes course)                                                            |
| `.eu` fact                                              | Scenario C (contradiction)                                                                   |

### 7.7 Expected results (write these as tests BEFORE building features)

**Scenario A:** `pricing.pro.monthly` 49 → 59, source `src:pricing_committee_memo_2026_10`.

- **Impacted facts:** `pricing.pro.annual` → `annual@v2 = 590` (rule `x10`), `DERIVED_FROM` points to `monthly@v2`.
- **Impacted documents (exactly 7):**

| Document              | Reason                                  | Path                                                               |
| --------------------- | --------------------------------------- | ------------------------------------------------------------------ |
| pricing_page          | CITES (+ CITES_DERIVED_FACT via annual) | `[pricing_page, monthly@v1]`                                     |
| sales_deck            | CITES                                   | `[sales_deck, monthly@v1]`                                       |
| faq                   | CITES                                   | `[faq, monthly@v1]`                                              |
| revenue_forecast_q4   | CITES                                   | `[revenue_forecast_q4, monthly@v1]`                              |
| support_macro_upgrade | DERIVED_FROM_DOC                        | `[support_macro_upgrade, faq, monthly@v1]`                       |
| investor_update       | DERIVED_FROM_DOC                        | `[investor_update, revenue_forecast_q4, monthly@v1]`             |
| board_deck            | DERIVED_FROM_DOC                        | `[board_deck, investor_update, revenue_forecast_q4, monthly@v1]` |

- **Never flagged by the graph:** refund_policy, onboarding_guide, careers_page, partner_faq.
- **WARN (`LITERAL_VALUE_LEAK`):** partner_faq only. careers_page must **not** appear; sales_deck's `$149` must not be rewritten.
- **Drafted edits:** `PROPOSE_EDIT` for pricing_page (`$49`→`$59`, `$490`→`$590`), sales_deck (`$49`→`$59`, `$149` untouched), faq, revenue_forecast_q4. `MARK_STALE` (NEEDS_REVIEW) for support_macro, investor_update, board_deck (no literal to replace). Agent notes that Arjun must recompute any MRR figures.
- **Owners to notify:** Maya, Ravi, Sofia, Arjun (+ Lena for the warning).
- **After merge:** monthly@v1/annual@v1 SUPERSEDED; @v2 ACTIVE; `SUPERSEDES` edges exist; the four edited docs now `CITES` the @v2 facts and are `CURRENT`; the three derived docs remain `NEEDS_REVIEW`; `STALE_DEPENDENCY` returns zero rows on `main`.

**Scenario B (invalid source):** same change with `src:slack_rumor_2026_10` → `SOURCE_INVALID` blocks; agent calls `request_verification`, drafts nothing, never submits.

**Scenario C (contradiction):** seed with `--with-contradiction` → `CONTRADICTION` (monthly vs `.eu`) blocks until a second `UPDATE_FACT` on `pricing.pro.monthly.eu` is added to the CR.

### 7.8 Keyword-vs-graph baseline (the "why a graph?" slide)

Implement `baseline.py`: naive keyword search for `49` over `Document.content`.

| Method                      | Finds                                                                                    | False positives | Misses                                     |
| --------------------------- | ---------------------------------------------------------------------------------------- | --------------- | ------------------------------------------ |
| Naive search "49"           | pricing_page, sales_deck, faq, revenue_forecast, partner_faq, **careers_page** (6) | careers_page    | support_macro, investor_update, board_deck |
| Exact `$49` regex         | pricing_page, sales_deck, faq, revenue_forecast, partner_faq (5)                         | none            | same 3                                     |
| **TruthBranch graph** | 7 documents + 1 fact, each with a path                                                   | none            | partner_faq (caught by the literal WARN)   |

Slide line: *"Keyword search missed 3 documents. The graph found them, and explained why."*

- [ ] `GET /api/change-requests/{id}/baseline` returns this comparison
- [ ] Test asserts the numbers above

### 7.9 Optional: `--scale N`

Seed script flag generating N filler documents with random citations and owners. Not for the demo; lets the README say "queries stay fast beyond toy size". Cut-list item.

---

## 8. Cypher query catalog

> Test each in FalkorDB Browser first. Items marked **⚠ verify** rely on list comprehensions, `nodes()`, `EXISTS {}`, or `FOREACH`. Keep a Python fallback for each.

### 8.1 Seeding (idempotent)

```cypher
UNWIND $people AS x
MERGE (p:Person {id: x.id})
SET p.name = x.name, p.role = x.role, p.email = x.email

UNWIND $facts AS x
MERGE (f:Fact {id: x.id})
SET f.key = x.key, f.version = x.version, f.subject = x.subject,
    f.attribute = x.attribute, f.value = x.value, f.unit = x.unit,
    f.status = x.status, f.created_at = x.created_at

UNWIND $cites AS x
MATCH (d:Document {id: x.doc}), (f:Fact {id: x.fact})
MERGE (d)-[:CITES]->(f)
```

### 8.2 Lineage

```cypher
MATCH (f:Fact {id:$fact_id})-[:SUPERSEDES*0..10]->(old:Fact)
RETURN old.id, old.version, old.value, old.status ORDER BY old.version DESC

MATCH (f:Fact {id:$fact_id})-[:SOURCED_FROM]->(s:Source)
RETURN s.id, s.title, s.valid, s.trust

MATCH (f:Fact {id:$fact_id})-[:DERIVED_FROM*1..3]->(u:Fact)
RETURN DISTINCT u.id, u.value
```

### 8.3 Impact (run against the branch)

```cypher
// 1) direct citers
MATCH (d:Document)-[:CITES]->(f:Fact {id:$old_fact_id}) RETURN d.id, d.title, d.status

// 2) downstream facts
MATCH (g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id}) RETURN DISTINCT g.id, g.key

// 3) documents citing downstream facts
MATCH (d:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id})
RETURN DISTINCT d.id, g.id AS via_fact

// 4) documents derived (transitively) from citers (the multi-hop story)
MATCH (d1:Document)-[:CITES]->(f:Fact {id:$old_fact_id})
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1)
RETURN DISTINCT d2.id, d1.id AS via_doc

// 5) readable path (⚠ verify nodes() + comprehension)
MATCH p = (d2:Document {id:$doc_id})-[:DERIVED_FROM*0..3]->(d1:Document)-[:CITES]->(f:Fact {id:$old_fact_id})
RETURN [n IN nodes(p) | n.id] AS path

// 6) owners and systems
MATCH (d:Document)-[:OWNED_BY]->(p:Person) WHERE d.id IN $doc_ids
OPTIONAL MATCH (d)-[:PUBLISHED_IN]->(s:System)
RETURN d.id, p.id, p.name, s.name
```

Implementation: run 1 to 4 and merge in Python into `{doc_id, title, owner, system, reasons[], path}`. Priority of primary reason: `CITES` > `CITES_DERIVED_FACT` > `DERIVED_FROM_DOC`. **Every flagged item must carry a reason and a path.** Also treat documents derived from documents citing a *downstream* fact (query 3 results) as affected.

### 8.4 Checks

```cypher
// SOURCE
MATCH (f:Fact {id:$new_fact_id})
OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s:Source)
RETURN f.id, count(s) AS source_count, collect(s.valid) AS valid_flags, collect(s.trust) AS trust_scores

// CONTRADICTION: two ACTIVE facts, same subject+attribute, different value
MATCH (a:Fact {status:'ACTIVE'}), (b:Fact {status:'ACTIVE'})
WHERE a.subject = b.subject AND a.attribute = b.attribute AND a.id < b.id AND a.value <> b.value
RETURN a.id, a.value, b.id, b.value

// DOCUMENT CANDIDATES for literal scan (filter by regex in Python)
MATCH (d:Document) OPTIONAL MATCH (d)-[:CITES]->(f:Fact {key:$key})
RETURN d.id, d.title, d.content, count(f) AS cites_key
```

- **STALE_DEPENDENCY** is computed in Python: `impact_set − (docs with PROPOSE_EDIT) − (docs/facts marked NEEDS_REVIEW)` must be empty.
- **LITERAL_VALUE_LEAK:** regex `(?<![\d,$])\$49(?!\d)` (escaped properly) over documents **outside** the impact set. Plain `CONTAINS "49"` is forbidden (it would flag careers_page and `$490`).

### 8.5 Merge (replayed on `kb_main`, per op)

```cypher
// UPDATE_FACT with optimistic version check
MATCH (old:Fact {key:$key, status:'ACTIVE'})
WHERE old.version = $expected_version
CREATE (new:Fact {id:$new_id, key:$key, version:$new_version, subject:old.subject,
                  attribute:old.attribute, value:$new_value, unit:old.unit,
                  status:'ACTIVE', created_at:$now})
CREATE (new)-[:SUPERSEDES]->(old)
SET old.status = 'SUPERSEDED'
RETURN new.id
// zero rows => base changed => abort the whole merge (CONFLICT)

// carry over owner (⚠ verify FOREACH; fallback: two simple queries)
MATCH (new:Fact {id:$new_id}), (old:Fact {id:$old_id})
OPTIONAL MATCH (old)-[:OWNED_BY]->(p:Person)
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (new)-[:OWNED_BY]->(p))

// REPOINT_CITATION (per approved edit)
MATCH (d:Document {id:$doc_id})-[c:CITES]->(old:Fact {id:$old_id})
MATCH (new:Fact {id:$new_id})
DELETE c
MERGE (d)-[:CITES]->(new)

// derived fact edge (annual@v2 -> monthly@v2)
MATCH (a:Fact {id:$new_derived_id}), (m:Fact {id:$new_base_id})
MERGE (a)-[r:DERIVED_FROM]->(m) SET r.rule = $rule
```

---

## 9. Change operations, branching, and merge

### 9.1 Operations (explicit, replayable, idempotent via `op_id` = hash of content)

| Op                   | Fields                                                         | Effect                                                                                      |
| -------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `UPDATE_FACT`      | `key, expected_version, new_value, derived?{from_key, rule}` | New version, `SUPERSEDES`, old `SUPERSEDED`; if `derived`, links to the new base fact |
| `ATTACH_SOURCE`    | `fact_id, source_id`                                         | Adds `SOURCED_FROM`                                                                       |
| `MARK_STALE`       | `node_id, reason`                                            | `status='NEEDS_REVIEW'` on a document or fact                                             |
| `PROPOSE_EDIT`     | `doc_id, before, after`                                      | Creates `ProposedEdit`                                                                    |
| `REPOINT_CITATION` | `doc_id, old_fact_id, new_fact_id`                           | Moves `CITES` on merge (auto-generated per approved edit)                                 |

For Scenario A the engine generates: `UPDATE_FACT monthly`, `ATTACH_SOURCE`, `UPDATE_FACT annual (derived, x10)`, `ATTACH_SOURCE` (annual).

### 9.2 Lifecycle

```
DRAFT ─analyze─► BLOCKED ◄──(recheck after edits/new source)──┐
   │                │                                          │
   │           recheck passes                                  │
   └─analyze─► CHECKS_PASSED ─submit (agent or button)─► READY_FOR_REVIEW
                                                              │
                                        approve ──► APPROVED ─┤─ merge ─► MERGED
                                        reject  ──► REJECTED  └─ conflict ─► CONFLICT
```

Legal transitions (each is a unit test):

| From                       | To                                  |
| -------------------------- | ----------------------------------- |
| DRAFT                      | BLOCKED, CHECKS_PASSED              |
| BLOCKED                    | BLOCKED, CHECKS_PASSED, REJECTED    |
| CHECKS_PASSED              | BLOCKED, READY_FOR_REVIEW, REJECTED |
| READY_FOR_REVIEW           | APPROVED, REJECTED, BLOCKED         |
| APPROVED                   | MERGED, CONFLICT                    |
| MERGED, REJECTED, CONFLICT | (terminal)                          |

Rules:

- [ ] `main` is **never** modified before `APPROVED`.
- [ ] `merge` only from `APPROVED`, and only if checks still pass.
- [ ] Merging twice is a no-op returning the existing result.
- [ ] If `Meta.revision` moved since branching **and** the target fact's version differs from `expected_version` → `CONFLICT`, zero writes.
- [ ] `submit` only from `CHECKS_PASSED`.

### 9.3 Branching strategy

**Plan:** Option A (graph copy). Everything is written around explicit ops so Option B (logical branch: compute impact on `main` with ops applied virtually) stays a drop-in fallback.

Day-1 spike, answer with evidence in `docs/branching-spike.md`:

- [ ] `kb_main.copy("kb_cr_test")` works from your client
- [ ] Writing to the branch does **not** change `kb_main` (counts before/after)
- [ ] The branch contains the indexes
- [ ] Deleting the branch works and leaves `kb_main` intact

### 9.4 Merge procedure

1. Load CR; verify `APPROVED`.
2. Re-run checks against the branch.
3. Compare `Meta.revision` with `base_revision`.
4. **Pre-validate** every op (read-only preconditions). Only if all pass, write. (No multi-query transaction: validate first, then write; keep each op a single query so it is atomic on its own.)
5. Replay ops in order on `kb_main` (facts first, then edges).
6. Apply approved `ProposedEdit`s to `Document.content`; run `REPOINT_CITATION`; set `status='CURRENT'` and `last_reviewed` for edited docs; leave `NEEDS_REVIEW` docs flagged.
7. Increment `Meta.revision`.
8. Write `AuditEvent(MERGED)`; CR → `MERGED`.
9. Delete the branch graph.

- [ ] Rejected CRs keep audit trail, delete the branch.

---

## 10. Quality checks (deterministic, no LLM)

Each returns `{code, severity: BLOCK|WARN, message, evidence: []}`.

| Code                      | Severity | Passes when                                                                            | Evidence            |
| ------------------------- | -------- | -------------------------------------------------------------------------------------- | ------------------- |
| `SOURCE_MISSING`        | BLOCK    | New fact has ≥1 `SOURCED_FROM`                                                      | fact id             |
| `SOURCE_INVALID`        | BLOCK    | All sources `valid=true` and `trust >= 0.6`                                        | source id, trust    |
| `STALE_DEPENDENCY`      | BLOCK    | Every item in the impact set is covered by a `PROPOSE_EDIT` or `NEEDS_REVIEW` mark | uncovered ids       |
| `CONTRADICTION`         | BLOCK    | No two ACTIVE facts share subject+attribute with different values                      | both ids and values |
| `LITERAL_VALUE_LEAK`    | WARN     | No document outside the impact set contains the old literal (regex)                    | doc ids             |
| `STALE_OWNER` (stretch) | WARN     | Every flagged doc has an owner                                                         | doc ids             |

`STALE_DEPENDENCY` is what forces the agent to draft edits.

---

## 11. The agent (Track 1 centerpiece)

### 11.1 Responsibilities

| Component              | Decides                                                                   |
| ---------------------- | ------------------------------------------------------------------------- |
| Graph                  | What is connected and affected                                            |
| Validation engine      | Whether rules pass                                                        |
| **Agent (Groq)** | **Which tool next, how to interpret results, when to stop and ask** |
| Human                  | Whether the change is authorized                                          |

### 11.2 Tools (Pattern A)

| Tool                                | Input                                | Output                                                   | Side effects                        |
| ----------------------------------- | ------------------------------------ | -------------------------------------------------------- | ----------------------------------- |
| `get_lineage`                     | `fact_id`                          | versions, sources (validity, trust), upstream facts      | none                                |
| `get_impact`                      | `cr_id`                            | affected docs/facts with reasons, paths, owners, systems | none                                |
| `run_checks`                      | `cr_id`                            | check results                                            | none                                |
| `propose_edits_for_affected_docs` | `cr_id`, optional `doc_ids`      | ProposedEdits and NEEDS_REVIEW marks                     | **branch only**               |
| `request_verification`            | `cr_id`, `reason`, `person_id` | confirmation record                                      | audit event; simulated notification |
| `submit_for_approval`             | `cr_id`                            | new status `READY_FOR_REVIEW`                          | only if state is `CHECKS_PASSED`  |
| `graph_explore` (stretch)         | question                             | rows                                                     | read-only text-to-Cypher            |

Hard limits (enforced in code, not the prompt):

- [ ] No tool writes to `kb_main`
- [ ] `submit_for_approval` refuses when any BLOCK check fails; refusal text returns to the model
- [ ] There is **no** merge tool and **no** approve tool (assert the tool list in a test)

### 11.3 Loop skeleton

```python
messages = [system_prompt, user_message(cr_summary)]
for step in range(MAX_STEPS):                  # 8
    resp = groq.chat.completions.create(model=MODEL, messages=messages,
                                        tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0)
    msg = resp.choices[0].message
    messages.append(msg)
    if not msg.tool_calls: break
    for call in msg.tool_calls:
        args = validate(call.function.name, call.function.arguments)   # Pydantic
        result = TOOLS[call.function.name](**args)                     # real Cypher
        log_agent_step(cr_id, step, call, summarize(result))
        messages.append({"role": "tool", "tool_call_id": call.id,
                         "content": truncate(json.dumps(result), 4000)})
```

### 11.4 System prompt must contain

- [ ] Role: "You review proposed knowledge changes. You never approve or merge."
- [ ] Schema card (labels, relationships, key properties)
- [ ] Workflow: lineage of the new fact first; if the source is unreliable, stop and call `request_verification`; otherwise `get_impact`, `run_checks`, draft edits, re-run checks, `submit_for_approval`; for WARN dark dependencies (partner_faq), call `request_verification` for the owner instead of editing
- [ ] Honesty rule: never claim readiness unless `run_checks` shows no BLOCK; cite only IDs from tool results
- [ ] Final report format: verdict, affected items with reasons, checks, what was drafted, what a human must decide (including numbers needing recompute, e.g. MRR)

### 11.5 What makes it a real agent

- **Scenario A:** `get_lineage → get_impact → run_checks (fail) → propose_edits → run_checks (pass) → request_verification (Lena, partner_faq) → submit_for_approval`.
- **Scenario B:** `get_lineage` shows `valid=false, trust=0.2` → agent **changes course**: `request_verification`, no drafting, no submit.

- [ ] UI shows each step: tool, arguments, short result, timestamp.

### 11.6 Drafting edits (reliable)

1. **Deterministic first:** regex replace old literal with new in `content` (`$49`→`$59`, `$490`→`$590` via the derivation rule). Use `(?<![\d,])\$49(?!\d)` so `$149` and `$490` are never hit by the monthly replace.
2. Document with **no literal** → `MARK_STALE` (NEEDS_REVIEW) plus owner notification.
3. **Optional LLM polish:** reject output that changes anything but price words (diff check).
4. Always store `before` and `after`.

### 11.7 Reliability fallbacks

- [ ] Retry once on malformed arguments; backoff on 429
- [ ] **`AGENT_MODE=scripted`**: runs the same tools in order without the LLM. README states honestly that it exists.
- [ ] Cache a successful Scenario A run to `docs/sample-run.json`
- [ ] Post-check: every `doc:`/`fact:` ID in the final text appeared in tool output

### 11.8 MCP (stretch only)

Expose the same tool functions via an MCP server. If it threatens delivery, skip and describe the architecture honestly.

---

## 12. API contract

| Method | Path                                       | Purpose                                                              |
| ------ | ------------------------------------------ | -------------------------------------------------------------------- |
| GET    | `/api/health`                            | App + FalkorDB connectivity                                          |
| POST   | `/api/admin/reset-demo`                  | Wipe branches/meta; reseed `kb_main` (`with_contradiction` flag) |
| GET    | `/api/facts/{fact_id}/lineage`           | Lineage                                                              |
| POST   | `/api/change-requests`                   | `{title, fact_key, new_value, source_id?}`; creates branch and ops |
| GET    | `/api/change-requests`                   | List                                                                 |
| GET    | `/api/change-requests/{id}`              | Full detail: status, ops, diff, impact, checks, edits, steps, audit  |
| POST   | `/api/change-requests/{id}/analyze`      | Deterministic impact + checks                                        |
| GET    | `/api/change-requests/{id}/baseline`     | Keyword-vs-graph comparison                                          |
| POST   | `/api/change-requests/{id}/agent-review` | Run the agent (SSE if time, else poll)                               |
| POST   | `/api/change-requests/{id}/submit`       | `CHECKS_PASSED → READY_FOR_REVIEW`                                |
| POST   | `/api/change-requests/{id}/approve`      | `{reviewer}`; only from `READY_FOR_REVIEW`                       |
| POST   | `/api/change-requests/{id}/reject`       | `{reviewer, reason}`                                               |
| POST   | `/api/change-requests/{id}/merge`        | Only from `APPROVED`                                               |

- [ ] Pydantic models for every request/response
- [ ] 404 unknown CR; 409 illegal transition or conflict; 422 validation
- [ ] CORS for the Vite dev origin
- [ ] Every state change writes an `AuditEvent`

---

## 13. Frontend screens

1. **Change Request page** (must be excellent)
   - [ ] Header: title, status badge, proposer
   - [ ] **Proposed change card:** key, `49 → 59`, source with validity/trust badge; derived fact `490 → 590`
   - [ ] **Impact table:** document, owner, system, reason, expandable path (`Board deck → Investor update → Q4 revenue forecast → pricing.pro.monthly@v1`)
   - [ ] **Baseline card:** "Keyword search found N, missed M; graph found 7 with reasons"
   - [ ] **Checks panel:** pass/warn/fail with evidence
   - [ ] **Agent timeline:** tool, arguments, summary, timestamp
   - [ ] **Proposed edits:** before/after diff per document
   - [ ] **Action bar:** Submit / Approve / Reject / Merge enabled only in the right state
   - [ ] **Main vs branch diff panel**
2. **New change form** (fact key dropdown, new value, source dropdown including the invalid one)
3. **Dashboard list**
4. **Reset demo** button
5. **Stretch:** compact graph-path visualization (cytoscape or react-flow)

Rules:

- [ ] A judge understands the screen without reading code
- [ ] Always show *why* each item is flagged
- [ ] Loading and error states everywhere (the agent takes seconds)
- [ ] If behind: drop styling and visualization, never the "why" paths

---

## 14. Sprints (IST)

Time boxes are ceilings. When one runs out, take the fallback and move on.

### Sprint 1: Thu 15 Oct (tonight): foundation and risk spikes (about 4 to 5 h)

**Goal:** a seeded graph with tested queries, and proof that branching works.

**Block 1.1 Environment (45 min)**

- [x] Repo, `README` stub, `LICENSE`, `.gitignore` (`.env`, `node_modules`, `__pycache__`)
- [x] Docker FalkorDB up. *Fallback:* FalkorDB Cloud.
- [x] Hand-run a throwaway `CREATE` + `MATCH` in the Browser
- [x] venv; install `fastapi uvicorn FalkorDB groq pydantic pydantic-settings python-dotenv pytest httpx`
- [x] `.env.example`: `FALKORDB_HOST, FALKORDB_PORT, GROQ_API_KEY, GROQ_MODEL, AGENT_MODE`
- [x] `/api/health` pings FalkorDB
- [x] **Exit:** health returns OK

**Block 1.2 Schema and dataset (75 min)**

- [x] `schema.py` (labels, rel types, ID helpers)
- [x] `seed/data.py` with **exactly Section 7** (distinct `.eu` key, 11 documents, `rule:'x10'` edge)
- [x] `seed.py` with `UNWIND + MERGE`, `reset()`, `--with-contradiction` flag
- [x] Indexes at the end
- [x] Seed twice; counts identical
- [x] Eyeball in the Browser

**Block 1.3 Core queries (75 min)**

- [x] `queries/*.py` from Section 8
- [x] Write `tests/test_ground_truth.py` from Section 7.7 **first**
- [x] `impact_for_fact(graph, fact_id)` merging queries 1 to 4 with `reasons` and `path`
- [x] Python fallback for any query that fails
- [x] Note on FalkorDB: always alias relationships when counting (`count(r)`) and use MERGE to prevent parallel duplicates.
- [x] **Exit:** prints exactly the 7 documents + annual fact; none of the 4 non-flagged documents

**Block 1.4 Branching spike (45 min, top risk)**

- [x] Answer the four questions in 9.3 into `docs/branching-spike.md`
- [x] Record **Option A or B**; record client version and Docker tag (Option A locked in)

**Block 1.5 Wrap-up (15 min)**

- [x] Commit and push to a **public** repo tonight
- [x] `NEXT.md` with tomorrow's first three tasks

**Done when:** repeatable seed, passing query tests, documented branching decision.
**If behind:** skip `LITERAL_VALUE_LEAK` and the contradiction flag until Sprint 2.

### Sprint 2: Fri 16 Oct: change engine (no LLM, no frontend, about 8 h)

**Block 2.1 Models and persistence (60 min)**

- [x] Pydantic models; `kb_meta` helpers; `AuditEvent`
- [x] `transition(cr, to)` per the table in 9.2; legal/illegal tests

**Block 2.2 Create CR and branch (60 min)**

- [x] `POST /change-requests`: validate fact is ACTIVE, capture `base_revision`, copy graph, build ops (including derived annual), save
- [x] Apply ops to the **branch**
- [x] Tests: branch has `@v2` for monthly and annual; `kb_main` still v1 only; two CRs make two independent branches

**Block 2.3 Deterministic diff (45 min)**

- [x] Diff `{key, old_value, new_value, old_id, new_id}` plus doc status changes; exact-match test

**Block 2.4 Impact and baseline (60 min)**

- [x] Wire `impact_for_fact` into `analyze`; owners/systems enrichment
- [x] `baseline.py` and endpoint; test numbers from 7.8
- [x] Distractors never appear

**Block 2.5 Checks (90 min)**

- [x] `SOURCE_MISSING`, `SOURCE_INVALID`, `STALE_DEPENDENCY` (over impact set), `CONTRADICTION`, `LITERAL_VALUE_LEAK` (regex)
- [x] Status after analyze: `BLOCKED` or `CHECKS_PASSED`
- [x] Scenario tests A, B, C

**Block 2.6 Deterministic edit proposals (45 min)**

- [x] Literal replace for docs with literals; `MARK_STALE` for those without
- [x] Assert `$149` untouched, `$490→$590`; re-run checks removes `STALE_DEPENDENCY`

**Block 2.7 Submit, approve, reject, merge (90 min)**

- [x] `submit`, `approve`, `reject`
- [x] `merge` per 9.4 including `REPOINT_CITATION`, derived edge, revision bump, branch delete
- [x] Conflict path; idempotent merge
- [x] Post-merge test: v1 SUPERSEDED, v2 ACTIVE, `SUPERSEDES` edges, docs updated and re-pointed, `STALE_DEPENDENCY` empty on `main`, history intact

**Block 2.8 Script the flow (30 min)**

- [x] `scripts/run_scenario_a.py`; commit and push

**Done when:** scenario script runs propose → branch → analyze → edits → submit → approve → merge with correct final `main`, no LLM, no frontend.
**If behind:** keep only `SOURCE_INVALID` and `STALE_DEPENDENCY`. Never drop approve/merge safety.

### Sprint 3: Sat 17 Oct: agent first, interface second

**Block 3.1 Tool layer (75 min)**

- [ ] Wrap services as tools with JSON schemas and Pydantic args; compact results
- [ ] Enforce hard limits (11.2); test tools directly

**Block 3.2 Groq loop (90 min)**

- [ ] Model ID in `.env`; `loop.py` (8 steps, truncation, backoff); system prompt (11.4); log `AgentStep`s
- [ ] Run A; tune **tool descriptions** (they matter more than the prompt)
- [ ] Run B; confirm refusal and `request_verification`
- [ ] `AGENT_MODE=scripted`

**Block 3.3 Agent endpoint (30 min)**

- [ ] `agent-review` returns report + steps (poll or single response)
- [ ] Post-check: cited IDs exist in tool output

**Block 3.4 Frontend (150 min)**

- [ ] Vite + React, `api.ts`, routes
- [ ] Section 13 in priority order; wire buttons by state; reset button

**Block 3.5 Browser end-to-end (45 min)**

- [ ] Scenario A and B fully in the browser; fix the first five annoying bugs only

**Block 3.6 Stretch (only if solid):** diff polish, graph-path view, MCP, `graph_explore`, `--scale`.

**Done when:** full browser flow with visible tool calls, paths, drafted edits, human approval, merge.
**If behind:** plain HTML tables; cut all stretch; if the agent is flaky by mid-afternoon, tighten tool descriptions, lower the step cap, make sure scripted mode works.

### Sprint 4: Sun 18 Oct: reliability and submission only

- 09:00 to 13:00 reliability and tests
- 13:00 to 15:30 docs and diagrams
- 15:30 to 17:30 demo video
- **17:30 to 18:00 submit**
- 18:00 to 23:59 emergency buffer only

**Block 4.1 Failure-case tests (90 min)**

- [ ] Failed validation never reaches approval
- [ ] Rejection leaves `kb_main` unchanged and deletes the branch
- [ ] Duplicate ops create no duplicate versions
- [ ] Merging twice is safe; merge on a changed base → `CONFLICT`, zero writes
- [ ] Wrong-state approve → 409
- [ ] **`kb_main` snapshot identical before approval**
- [ ] Agent tool list contains no merge/approve

**Block 4.2 Clean-room run (60 min)**

- [ ] Fresh clone; follow README only; fix every improvisation

**Block 4.3 Documentation (150 min)**

- [ ] `README.md` (Section 17), `docs/graph-schema.md`, `docs/cypher-queries.md`, `docs/architecture.md` with diagram
- [ ] Screenshots (Scenario A and B)
- [ ] AI usage disclosure
- [ ] Limitations: single branch at a time, synthetic data, scripted mode, `partner_faq` caught only by literal scan

**Block 4.4 Demo video (120 min)**

- [ ] Follow Section 16; 3 to 5 min; re-record rather than edit heavily
- [ ] Upload and **open the link in a private window**

**Block 4.5 Submission (30 min, before 18:00)**

- [ ] Repo public (verify logged out); both tracks named; README has setup + data model; Cypher documented; video works; AI disclosure; re-read the rules page once more

---

## 15. Cut list (drop in this order)

1. Graph visualization
2. MCP exposure
3. `graph_explore`
4. SSE streaming
5. `LITERAL_VALUE_LEAK`, `STALE_OWNER`
6. LLM polish of edit text
7. `--scale` seeding
8. Contradiction scenario (keep as documented extension)
9. Option A branching → Option B
10. UI styling (never the "why" paths)

**Never cut:** impact analysis with reasons, baseline comparison, checks, human approval, safe merge with history, the agent tool loop (even with 3 tools), README + video + public repo.

---

## 16. Testing checklist

**Graph**

- [ ] Seed idempotent
- [ ] Impact returns exactly the 7 documents + annual fact (7.7)
- [ ] refund_policy, onboarding_guide, careers_page, partner_faq never in the impact set
- [ ] board_deck path has 4 nodes; investor_update path has 3
- [ ] Lineage ordered correctly
- [ ] Baseline numbers match 7.8

**Branching and merge**

- [ ] Branch isolation; main unchanged before approval
- [ ] After merge: v1 SUPERSEDED, v2 ACTIVE, `SUPERSEDES` present, audit written, `CITES` re-pointed, no stale deps on `main`
- [ ] Conflict path; merge idempotent

**Checks**

- [ ] A blocks until edits drafted, then passes; B blocks on `SOURCE_INVALID`; C blocks on `CONTRADICTION` until the regional fact is updated
- [ ] `LITERAL_VALUE_LEAK` flags partner_faq only; `$149` untouched

**Agent**

- [ ] Sensible A sequence; only real IDs in the final text
- [ ] B refuses to claim readiness
- [ ] Malformed arguments handled; step cap enforced; scripted mode works with no key

**Product**

- [ ] Browser flow A and B; reset in seconds; clean-room setup succeeds

---

## 17. Demo script (3 to 5 min)

1. **(0:00 to 0:30) Problem.** A price changes in one place and stays wrong in a dozen others.
2. **(0:30 to 1:00) Idea.** Git for company knowledge: branch, diff, review, merge, on a FalkorDB graph. Say once: "synthetic Lumen Analytics dataset, designed with known ground truth".
3. **(1:00 to 1:30) Graph.** Facts, documents, owners; point at `CITES`, `DERIVED_FROM`, `SUPERSEDES`.
4. **(1:30 to 3:00) Scenario A.** `$49 → $59` with a valid source. Show the branch diff, the impact table (open the **board_deck** path), the **baseline card** ("keyword search missed 3"), the failed check, the agent timeline (edits drafted, `partner_faq` verification, checks pass). Stop at the gate: "The agent cannot merge. A human does."
5. **(3:00 to 3:30) Approve and merge.** `main` updated; v1 superseded, v2 active; derived docs still flagged for review.
6. **(3:30 to 4:15) Scenario B.** Slack source: the agent sees `valid=false, trust=0.2`, changes course, requests verification, refuses to submit.
7. **(4:15 to 4:45) Why FalkorDB.** Multi-hop traversal, lineage chains, graph copy for branches, all readable Cypher.
8. **(4:45 to 5:00) Close.** "Company knowledge you can version, review, and trust."

- [ ] Rehearse twice and time it; reset-demo before each take; keep `sample-run.json` ready

---

## 18. README outline and submission checklist

**README:** 1 pitch + screenshot · 2 tracks (1 and 3) and how · 3 why FalkorDB · 4 architecture diagram · 5 **graph data model** · 6 **essential Cypher** (link) · 7 quick start · 8 scenarios A/B/C · 9 agent design (tools, guardrails, scripted mode) · 10 testing + ground-truth table · 11 limitations · 12 AI usage disclosure · 13 license.

**Final checklist**

- [ ] Public repo (verified logged out)
- [ ] README with setup and data model; Cypher documented
- [ ] Demo video accessible
- [ ] Both tracks named
- [ ] AI disclosure; you can explain every part of the code
- [ ] No secrets (search history for `GROQ_API_KEY`)
- [ ] Submitted before 6:00 PM IST on 18 Oct

---

## 19. Risk register and troubleshooting

| Risk                                                                         | Likelihood | Mitigation                                              |
| ---------------------------------------------------------------------------- | ---------- | ------------------------------------------------------- |
| FalkorDB unfamiliarity                                                       | High       | Browser-first testing; tiny dataset; Python fallbacks   |
| Copy-based branching misbehaves                                              | Medium     | Day-1 spike; Option B; ops-based design                 |
| Unsupported Cypher (`nodes()`, comprehensions, `FOREACH`, `EXISTS {}`) | Medium     | Check on first use; compute in Python                   |
| Groq tool calls malformed                                                    | Medium     | Pydantic, one retry, temp 0, step cap, scripted mode    |
| Groq rate limits while recording                                             | Medium     | Backoff, cached run, off-peak recording                 |
| UI time balloons                                                             | High       | Tables first; cut list                                  |
| Scope creep                                                                  | High       | Section 2.3 and 15; no new features Sunday              |
| Merge writes partially                                                       | Low        | Pre-validate then write; idempotent ops; audit          |
| Demo breaks live                                                             | Medium     | Reset button, scripted mode, pre-recorded fallback take |

**Troubleshooting**

- *Empty results:* check the selected graph name, label spelling, and `'ACTIVE'` vs `'Active'`.
- *"Graph not found":* seed first.
- *Syntax error:* paste into the Browser; reduce to the smallest failing piece.
- *Duplicates after re-seed:* you used `CREATE` instead of `MERGE`.
- *Slow responses:* it is the LLM call, not the database.
- *Model invents IDs:* tighten the prompt, return real IDs in tool results, keep the post-check.
- *Wrong fact superseded:* check for duplicate ACTIVE keys (the v1 `.eu` collision).

---

### Final reminder

Tonight's job is to prove four things: FalkorDB runs, the dataset seeds repeatably, impact queries return exactly the 7 expected documents, and a branch copy is isolated from `main`. After that, everything is ordinary engineering on tested ground.
