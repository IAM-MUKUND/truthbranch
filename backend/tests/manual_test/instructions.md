# TruthBranch — Comprehensive Manual Testing Guide & Pre-Demo Preparation

> **Target Audience:** Testers, developers, and demo presenters.  
> **Location:** `backend/tests/manual_test/instructions.md`  
> **Platform Version:** TruthBranch v0.4.0 (FalkorDB + FastAPI + React 19)

---

## 1. Why Manual Testing is Essential Before Submission

While TruthBranch has **127 automated tests passing** (93 platform invariants + 34 ground-truth graph oracle tests), automated unit tests only test backend contracts. Manual end-to-end testing is critical for four strategic reasons:

1. **Verify Visual State Transitions in Real Time:**
   Ensure UI elements (interactive diff viewer, multi-hop path trees, baseline comparison cards, agent timeline progress, and approval buttons) reflect backend state transitions without UI race conditions.
2. **Validate the Live "Customer-to-Admin" Closed Loop:**
   The single most persuasive demonstration in the hackathon is asking the customer chatbot a question, updating the knowledge on an isolated branch, merging it, and asking the chatbot again to see the updated grounded answer and citation.
3. **Guard Against Edge-Case Failure During Video Recording:**
   Testing the exact presets and click sequences ahead of time guarantees smooth, uninterrupted recording for the 3-to-5 minute submission video.
4. **Verify Safety Invariants in the UI:**
   Confirm that the UI strictly disables approval and merge buttons when an unverified source (Scenario B) triggers a `BLOCK` check.

---

## 2. Environment Verification & Clean-Slate Setup

Before beginning the manual testing walkthrough, verify that all three system tiers are running properly:

### 2.1. Verify Services
1. **FalkorDB Container:**
   ```bash
   docker ps | grep truthbranch-falkordb
   ```
   *Expected:* Container running, port mapped to `6380:6379`.
2. **FastAPI Backend Server:**
   ```bash
   curl http://localhost:8000/api/health
   ```
   *Expected:* `{"status": "ok", "falkordb": "connected", "agent_mode": "groq"}`.
3. **Frontend Vite Dev Server:**
   Open `http://localhost:5173` in Google Chrome or Brave.
   *Expected:* TruthBranch Customer Knowledge Portal loads cleanly with zero console errors.

### 2.2. Clean-Slate Reset
To start from a guaranteed clean ground-truth state:
- Either click the **"Reset Lumen Demo"** button in the top-right navigation bar of the Admin Console,
- Or execute via terminal:
  ```bash
  .venv/bin/python -m backend.app.seed.seed --dataset lumen
  ```

---

## 3. Step-by-Step Manual Test Protocol

Follow these 6 structured test cases in exact chronological order:

---

### Test Case 1: Customer Assistant Baseline Query
* **Goal:** Verify that the public-facing customer AI assistant retrieves active production knowledge with grounded citations before any modifications are made.
* **Why this test matters:** Establishes the authoritative "Before" baseline.

| Step | Action | Expected Visual & Behavioral Result |
| :---: | :--- | :--- |
| **1.1** | Navigate to `http://localhost:5173/` (Customer Portal). | Customer chat interface loads with suggested prompts. |
| **1.2** | Click or type: **"How much does the Pro plan cost?"** and submit. | The assistant sends a request to `POST /api/chat`. |
| **1.3** | Inspect the chatbot response. | Bot answers: **"Lumen Pro costs $49 per month..."** with a badge citation to `[doc:faq]` or `[doc:pricing_page]`. |
| **1.4** | Click the citation badge `[doc:faq]`. | Citation details expand showing the verified ground-truth excerpt. |

---

### Test Case 2: Scenario A — Governed Price Change ($49 → $59)
* **Goal:** Test the complete "Git for Company Knowledge" lifecycle: branch creation, multi-hop impact analysis, baseline comparison, autonomous agent drafting, and human approval.
* **Why this test matters:** This is the core hero demo showing why connected graph data outperforms keyword search.

| Step | Action | Expected Visual & Behavioral Result |
| :---: | :--- | :--- |
| **2.1** | Navigate to `http://localhost:5173/admin` (Admin Console). | The Governance Console loads showing active dataset (`Lumen Analytics`). |
| **2.2** | Under **"Create Change Request"**, click preset **"Scenario A"**. | Form autofills: <br/>- Fact: `pricing.pro.monthly`<br/>- New Value: `59`<br/>- Source: `src:pricing_committee_memo_2026_10` (Trust: 0.95, Valid: True). |
| **2.3** | Click **"Create Change Request"**. | FalkorDB executes `GRAPH.COPY` in under 15ms. Candidate branch `kb_cr_<id>` is created. CR appears with status badge `DRAFT`. |
| **2.4** | View the **Visual Diff Viewer**. | Shows Fact Diff: `pricing.pro.monthly` ($49 → $59) and derived fact `pricing.pro.annual` ($490 → $590 via rule `x10`). |
| **2.5** | Inspect the **Impact Blast Radius Table**. | Displays **7 impacted documents** and **1 derived fact**. |
| **2.6** | Click on `doc:board_deck` to expand the **"Why Path"**. | Tree visualizes the 4-hop chain: <br/>`doc:board_deck` → `doc:investor_update` → `doc:revenue_forecast_q4` → `fact:pricing.pro.monthly@v1`. |
| **2.7** | Inspect the **Baseline Comparison Card**. | Shows comparison stats: <br/>- Keyword search (`"49"`) found 4 docs and **missed 3 critical documents** (`support_macro_upgrade`, `investor_update`, `board_deck`).<br/>- FalkorDB Graph blast radius found all 7 (100% recall). |
| **2.8** | Click **"Run Agent Analysis"**. | The autonomous Groq AI agent executes its ReAct loop: <br/>1. Runs checks (detects unaddressed impact).<br/>2. Drafts deterministic text edits for `pricing_page`, `sales_deck`, and `faq`.<br/>3. Marks unliteral docs (`support_macro_upgrade`, `investor_update`, `board_deck`) as `NEEDS_REVIEW`.<br/>4. Evaluates checks (all pass).<br/>5. Submits for review. |
| **2.9** | Inspect the **Agent Timeline & Checks Banner**. | All checks show green `PASS`. CR status transitions to `READY_FOR_REVIEW`. The **"Approve & Merge"** button becomes active. |
| **2.10** | Click **"Approve & Merge"**. | Status changes to `APPROVED` then `MERGED`. Production revision increments (`m.revision = 2`). Candidate branch `kb_cr_<id>` is safely deleted. |

---

### Test Case 3: Customer Assistant Post-Merge Verification (The Closed Loop)
* **Goal:** Verify that merged changes immediately propagate to customer-facing answers with zero manual sync.
* **Why this test matters:** Proves that company knowledge is dynamic, authoritative, and synchronized in production.

| Step | Action | Expected Visual & Behavioral Result |
| :---: | :--- | :--- |
| **3.1** | Return to the Customer Portal (`http://localhost:5173/`). | Chat interface is visible. |
| **3.2** | Type: **"How much does the Pro plan cost now?"** and submit. | The assistant reads updated active facts from `kb_main`. |
| **3.3** | Inspect the chatbot answer. | Bot immediately answers: **"$59 per month"** with an updated citation to `[doc:pricing_page]`. |
| **3.4** | Confirm absence of hallucinations. | Verify the bot does not claim $49 and cites only valid graph nodes. |

---

### Test Case 4: Scenario B — Security Guardrail (Unverified Slack Rumor)
* **Goal:** Verify that unverified or low-trust evidence is strictly blocked and cannot be merged by an agent.
* **Why this test matters:** Demonstrates governance safety and prevents bad data ingestion.

| Step | Action | Expected Visual & Behavioral Result |
| :---: | :--- | :--- |
| **4.1** | In the Admin Console (`/admin`), click preset **"Scenario B"**. | Form fills with Slack rumor source (`src:slack_rumor_2026_10`, Trust: 0.20, `valid: false`). |
| **4.2** | Click **"Create Change Request"**. | New branch is created in `DRAFT`. |
| **4.3** | Click **"Run Agent Analysis"**. | Agent runs quality checks. Check `SOURCE_INVALID` triggers with `severity: BLOCK`. |
| **4.4** | Inspect the result. | The agent **refuses to submit** for approval. CR status transitions to `BLOCKED`. |
| **4.5** | Verify UI Gate. | The **"Approve & Merge" button remains strictly disabled**. Bad data cannot enter production. |

---

### Test Case 5: Multi-Tenant Dataset Catalog Switching
* **Goal:** Verify that TruthBranch supports switching between independent company knowledge graphs with zero data collisions.
* **Why this test matters:** Proves enterprise multi-tenancy and data isolation in FalkorDB.

| Step | Action | Expected Visual & Behavioral Result |
| :---: | :--- | :--- |
| **5.1** | In the Admin Console top bar, locate the **Company Dataset Selector**. | Shows `Lumen Analytics (Active)`. |
| **5.2** | Select **"Meridian Systems"** and click **"Switch Company"**. | Backend executes `/api/admin/datasets/activate` for `meridian`. Ingests 574 nodes and 1,499 edges if not already present. |
| **5.3** | Verify Entity Dropdowns. | The entity selection dropdowns immediately populate with Meridian's 30 employees (e.g. *Anika Sharma*, *Samir Qureshi*) and 106 facts. |
| **5.4** | Switch back to **"Lumen Analytics"**. | Seamlessly switches active pointer back to `kb_main` (29 nodes, 41 edges) with zero duplicate nodes. |

---

### Test Case 6: Invariant & Failure-Case Verification
* **Goal:** Confirm state-machine and concurrency failure handling.

| Step | Action | Expected Result |
| :---: | :--- | :--- |
| **6.1** | **Direct Approve on Blocked CR:** Attempt to approve a `BLOCKED` Change Request via API. | Returns HTTP 400 (`Cannot approve Change Request in state 'BLOCKED'`). |
| **6.2** | **Optimistic Concurrency Conflict:** Attempt to merge a Change Request whose base revision has moved. | Merge aborts with zero writes, status updates to `CONFLICT`. |
| **6.3** | **Rejection Cleanup:** Click "Reject" on any active draft. | CR status updates to `REJECTED`, candidate branch container is deleted from FalkorDB. |

---

## 4. Quick Troubleshooting & Recovery Playbook

| Symptom | Probable Cause | Immediate Remediation |
| :--- | :--- | :--- |
| **Frontend shows "Cannot connect to backend"** | Uvicorn server is not running on port 8000. | Run `.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`. |
| **Backend logs `ConnectionRefusedError: [Errno 111]`** | FalkorDB Docker container stopped. | Run `docker start truthbranch-falkordb` or restart container on port `6380:6379`. |
| **Agent review returns HTTP 429 (Rate Limit)** | Groq free tier per-minute token limit exceeded. | TruthBranch's `groq_pool.py` will automatically rotate keys. If all keys expire, it falls back to **Deterministic Scripted Mode** with zero interruption. |
| **State out of sync or test data corrupted** | Incomplete manual test left dirty state. | Click **"Reset Lumen Demo"** in the UI navigation bar to wipe and re-seed in 1.2s. |

---

## 5. Pre-Demo Video Recording Checklist

Before hitting the record button:
- [ ] Browser window zoomed to **110% or 125%** for sharp text readability at 1080p.
- [ ] Two tabs arranged:
  - **Tab 1:** Customer Knowledge Portal (`http://localhost:5173/`)
  - **Tab 2:** Admin Governance Console (`http://localhost:5173/admin`)
- [ ] Database freshly reset via **"Reset Lumen Demo"**.
- [ ] Timer/stopwatch ready (aim for **3:45 to 4:30** minutes).
- [ ] Script reference open: [docs/demo-video-guide.md](file:///home/mukundvinayak/truthbranch/docs/demo-video-guide.md).
