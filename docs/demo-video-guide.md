# TruthBranch — Official Demo Video Script & Recording Guide (3–5 Minutes)

> **Submission Requirement:** 3 to 5 minutes strictly. Keep the recording concise, clear, and high-energy. Re-record rather than doing heavy video editing.

---

## 1. Pre-Recording Checklist & Environment Setup

Before pressing record:
1. **FalkorDB Running:** Ensure FalkorDB container is running on port 6380 (`docker ps`).
2. **Backend & Frontend Running:**
   - Backend on `http://localhost:8000`
   - Frontend on `http://localhost:5173`
3. **Clean-Slate Reset:** Click **"Reset Lumen Demo"** in the top navigation or execute:
   ```bash
   .venv/bin/python -m backend.app.seed.seed --dataset lumen
   ```
4. **Browser Setup:**
   - Have two browser tabs ready:
     - **Tab 1:** Customer Knowledge Portal (`http://localhost:5173/`)
     - **Tab 2:** Admin Governance Console (`http://localhost:5173/admin`)
   - Zoom browser to 110% or 125% for high readability on 1080p video.
   - Close all bookmarks and extraneous tabs.
5. **Microphone Check:** Ensure clear audio without background noise.

---

## 2. Second-by-Second Video Script

| Timestamp | Screen Focus | Narration & Action Guide |
| :--- | :--- | :--- |
| **0:00 – 0:30** | Tab 1: Customer Portal (`/`) | **The Problem:**<br/>*"In every modern company, critical knowledge is scattered across Notion, pitch decks, FAQs, CRM macros, and financial forecasts. When a price or policy changes in one place, it stays wrong in a dozen others, leading to confused customers and silent revenue leaks."* |
| **0:30 – 0:50** | Tab 1: Customer Portal (`/`) | **The Live Customer Assistant (Baseline):**<br/>**Action:** Type in chat: *"How much does the Pro plan cost?"*<br/>**Bot Response:** Shows **$49 per month** with citation `[doc:faq]`.<br/>*Narration:* *"Here is our customer-facing AI assistant. It answers questions grounded directly in company knowledge with verified citations. Right now, it knows Pro is $49/month. Let's see what happens when the business decides to raise that price to $59."* |
| **0:50 – 1:20** | Tab 2: Admin Console (`/admin`) | **The Core Idea: Git for Company Knowledge:**<br/>*Narration:* *"Welcome to TruthBranch. We treat company knowledge just like source code: you branch, investigate downstream impact, autonomously draft follow-up edits, validate against governance checks, human-review, and merge. All built on top of FalkorDB with a synthetic ground-truth dataset."* |
| **1:20 – 2:00** | Tab 2: Admin Console (`/admin`) | **Scenario A: Pro Plan $49 → $59:**<br/>**Action:** Select **Scenario A** from quick presets (`pricing.pro.monthly`, new value `59`, memo source) and click **"Create Change Request"**.<br/>*Narration:* *"Notice what happened instantly: FalkorDB used GRAPH.COPY in under 10 milliseconds to create a completely isolated candidate branch. The production database is untouched."* |
| **2:00 – 2:40** | Tab 2: Diff & Impact View | **Graph Impact vs Keyword Baseline:**<br/>**Action:** Scroll to **Impact Analysis** and expand the **Board Deck** path.<br/>*Narration:* *"Look at the blast radius. Changing this single fact impacts 7 documents and 1 derived annual fact. The Board Deck is 4 hops away: from monthly price → revenue forecast → investor update → board deck.<br/>Notice our Baseline Comparison card: traditional keyword search found only 4 documents and missed 3 critical downstream documents completely! FalkorDB caught all 7."* |
| **2:40 – 3:20** | Tab 2: Agent Timeline | **Autonomous Agent Reasoning Loop:**<br/>**Action:** Click **"Run Agent Analysis"**.<br/>*Narration:* *"Our Groq-powered AI agent starts its ReAct loop. It inspects the graph, detects that 7 documents have unaddressed impact, and automatically drafts precise text edits for the Pricing Page, Sales Deck, and FAQ, while marking the financial models as needing review. It also runs our literal scan to detect shadow mentions in the Partner FAQ."* |
| **3:20 – 3:45** | Tab 2: Approval Gate | **The Human-in-the-Loop Gate:**<br/>**Action:** Point mouse to the checks passing banner and the **"Approve & Merge"** button.<br/>*Narration:* *"All governance checks have passed. But notice this crucial architectural boundary: The AI Agent CANNOT merge to production. It can only propose. A human must review and approve."*<br/>**Action:** Click **"Approve & Merge"**. |
| **3:45 – 4:05** | Tab 1: Customer Portal (`/`) | **The Full Loop: Instant Grounded Truth:**<br/>**Action:** Switch back to Customer Portal (Tab 1).<br/>**Action:** Type: *"How much does the Pro plan cost now?"*<br/>**Bot Response:** Immediately answers **$59 per month** with citation `[doc:pricing_page]`!<br/>*Narration:* *"The merge is complete. We return to the customer chatbot, ask the exact same question, and instantly it answers $59 per month with an updated verified citation. Zero stale knowledge. Full provenance."* |
| **4:05 – 4:35** | Tab 2: Admin Console (`/admin`) | **Scenario B: Unverified Source Blocked:**<br/>**Action:** Switch back to Admin Console, select **Scenario B** (Slack rumor source), and click **"Create Change Request"** and **"Run Agent Analysis"**.<br/>*Narration:* *"Now let's test safety. Scenario B proposes the same price change, but backed by an unverified Slack message with a 0.2 trust score. The agent runs checks, detects SOURCE_INVALID, refuses to submit, and leaves the Change Request in a BLOCKED state. Bad data never reaches production."* |
| **4:35 – 5:00** | Tab 2: Architecture / Overview | **Why FalkorDB & Close:**<br/>*Narration:* *"Why FalkorDB? Because it gives us sub-10ms graph-copy branching, lightning-fast multi-hop GraphBLAS matrix traversals, and readable Cypher queries without expensive relational joins.<br/>TruthBranch: Company knowledge you can version, review, and trust. Thank you!"* |

---

## 3. Rehearsal Tips & Fallback Protocols

- **Timer on Phone:** Keep a stopwatch running next to your monitor. Aim for 4 minutes 15 seconds to allow natural speaking cadence.
- **If Groq API experiences latency:** TruthBranch has an integrated **Groq API Key Pool** with automatic round-robin and 429 failover. Furthermore, if internet connectivity fluctuates, TruthBranch seamlessly falls back to **Deterministic Scripted Mode** with identical output.
- **If a misclick occurs:** Simply click the top-right **"Reset Lumen Demo"** button; it wipes and re-seeds the entire database in under 1 second.
- **After Recording:** Open the video file in VLC or an incognito browser window to verify clear audio, 1080p resolution, and that text is easily readable.
