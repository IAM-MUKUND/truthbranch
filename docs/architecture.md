# TruthBranch — System Architecture Specification

TruthBranch implements **"Git for Company Knowledge"** — an enterprise knowledge governance platform built on **FalkorDB** that enables organizations to branch, investigate, autonomously draft follow-up updates, validate, review, and merge knowledge changes with complete auditability.

---

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph Frontend["React 19 + TypeScript + Vite UI"]
        CustomerPortal["Customer Knowledge Portal<br/><code>/</code><br/>(Natural Language Q&A + Verified Citations)"]
        AdminPortal["Admin Governance Console<br/><code>/admin</code><br/>(Branch, Diff, Impact, Agent Loop, Human Approval)"]
    end

    subgraph Backend["FastAPI Application Server"]
        ChatRouter["Chat Router<br/>(Passive Guardrails & Whitelist Verification)"]
        CRRouter["Change Request Router<br/>(Branching, Diff, Agent Runner, Approval)"]
        AdminRouter["Admin & Dataset Router<br/>(Catalog Ingestion, Reset, Concurrency)"]
        
        subgraph AgentSubsystem["Groq Autonomous AI Agent Subsystem"]
            GroqPool["Groq API Key Pool<br/>(Round-Robin + 429 Failover)"]
            AgentLoop["ReAct Tool Calling Loop<br/>(Impact, ReadDoc, Checks, DraftEdit, MarkStale)"]
            ScriptedMode["Deterministic Scripted Fallback<br/>(Offline / No API Key)"]
        end
    end

    subgraph FalkorDB["FalkorDB Graph Storage Engine"]
        KBMain[("<code>kb_main</code><br/>Authoritative Production Graph<br/>(Facts, Docs, Lineage, Owners)")]
        KBBranch[("<code>kb_cr_&lt;id&gt;</code><br/>Isolated Candidate Branch<br/>(Deep cloned via <code>GRAPH.COPY</code>)")]
        KBMeta[("<code>kb_meta</code><br/>Governance & Audit Graph<br/>(ChangeRequests, AuditEvents, AgentSteps)")]
        KBCatalog[("<code>kb_cloudgrid</code><br/>Isolated Multi-Tenant Catalog")]
    end

    CustomerPortal -->|POST /api/chat| ChatRouter
    AdminPortal -->|REST API Calls| CRRouter
    AdminPortal -->|POST /api/admin/datasets| AdminRouter

    ChatRouter -->|Read-Only Cypher Query| KBMain
    CRRouter -->|Branch Clone / Replay Merge| FalkorDB
    AgentSubsystem -->|Read / Draft on Branch| KBBranch
```

---

## 2. Multi-Graph Topology in FalkorDB

To provide mathematically isolated branches without schema corruption or read contention, TruthBranch uses FalkorDB's native multi-graph capabilities:

| Graph Identifier | Role | Lifecycle | Mutability |
| :--- | :--- | :--- | :--- |
| `kb_main` *(or `kb_<company>`)* | **Production Ground Truth** | Persistent | Read-only to readers/chat; written **only** during atomic merge by an authorized human. |
| `kb_cr_<id>` | **Candidate Branch** | Ephemeral | Created via `GRAPH.COPY kb_main kb_cr_<id>`. Modified by agent and checks during validation. Deleted upon merge or rejection. |
| `kb_meta` | **Audit & Governance Store** | Persistent | Stores state machine status, audit event logs, agent reasoning traces, and active dataset pointers. |
| `kb_cloudgrid` | **Catalog Isolation** | Persistent | Standalone graph instance for secondary tenant (CloudGrid Infrastructure) to demonstrate multi-company switching without data collision. |

---

## 3. Change Request Lifecycle & State Machine

Every knowledge mutation follows a strict finite state machine (FSM). Unauthorized transitions are rejected with HTTP 400 or 409.

```mermaid
stateDiagram-v2
    [*] --> DRAFT: POST /api/change-requests
    DRAFT --> BRANCHED: GRAPH.COPY kb_main kb_cr_<id>
    BRANCHED --> ANALYZING: Agent runs impact analysis
    ANALYZING --> BLOCKED: Validation checks fail (e.g. Unverified Source)
    ANALYZING --> CHECKS_PASSED: All checks pass
    BLOCKED --> ANALYZING: New edits / evidence added
    CHECKS_PASSED --> READY_FOR_REVIEW: Agent drafts edits & marks stale
    READY_FOR_REVIEW --> APPROVED: Human Reviewer approves
    APPROVED --> MERGED: Atomic merge into kb_main (Branch deleted)
    
    DRAFT --> REJECTED: User cancels
    BLOCKED --> REJECTED: Human rejects
    READY_FOR_REVIEW --> REJECTED: Human rejects
    BRANCHED --> CONFLICT: Base revision moved (Optimistic Concurrency)
    
    MERGED --> [*]
    REJECTED --> [*]
    CONFLICT --> [*]
```

### State Machine Rules
1. **Approval Invariant:** A Change Request **can only** transition to `APPROVED` from `READY_FOR_REVIEW`.
2. **Rejection Cleanup:** Transitioning to `REJECTED` permanently deletes the candidate branch graph `kb_cr_<id>` and logs the human rejection reason in `kb_meta`.
3. **Optimistic Concurrency:** If `kb_main`'s global revision has incremented past the Change Request's `base_revision`, attempting to merge triggers a `CONFLICT` state and aborts with zero writes.

---

## 4. Groq Autonomous AI Agent Subsystem

The autonomous agent is designed around a **Strict Tool Boundary**:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Human Administrator
    participant UI as Admin Console
    participant Backend as TruthBranch API
    participant Agent as Groq AI Agent
    participant Branch as FalkorDB (kb_cr_<id>)
    participant Main as FalkorDB (kb_main)

    Admin->>UI: Create Change Request (Scenario A: $49 -> $59)
    UI->>Backend: POST /api/change-requests
    Backend->>Branch: GRAPH.COPY kb_main kb_cr_<id>
    UI->>Backend: POST /api/change-requests/{id}/run-agent
    
    loop ReAct Autonomous Reasoning Loop
        Agent->>Branch: Tool: impact_analysis(old_fact_id)
        Branch-->>Agent: 7 impacted documents + 1 derived fact
        Agent->>Branch: Tool: run_checks()
        Branch-->>Agent: UNADDRESSED_IMPACT (7 docs unedited)
        Agent->>Branch: Tool: read_document(doc_id)
        Agent->>Branch: Tool: draft_edit(doc_id, new_text)
        Agent->>Branch: Tool: mark_stale(doc_id, reason)
        Agent->>Branch: Tool: run_checks()
        Branch-->>Agent: Checks Passed: true
    end

    Agent-->>Backend: Mark Status: READY_FOR_REVIEW
    Backend-->>UI: Display Diff, Impact Paths & Ready Status
    
    Note over Admin,Agent: CRITICAL GATE: The AI Agent CANNOT approve or merge!
    Admin->>UI: Click "Approve & Merge"
    UI->>Backend: POST /api/change-requests/{id}/approve
    UI->>Backend: POST /api/change-requests/{id}/merge
    Backend->>Main: Atomic Replay: Supersede v1, insert v2, re-point CITES
    Backend->>Branch: branch.delete()
    Backend-->>UI: Merge Complete (Revision bumped)
```

### Key Pool & Fallback Mechanics
- **Groq API Pool (`groq_pool.py`):** Automatically discovers all `GROQ_API_KEY*` variables from `.env`, deduplicates them, and dispatches requests in a round-robin cycle.
- **Failover on Rate Limit:** On receiving HTTP 429 (Rate Limit Exceeded), the pool transparently switches to the next available key without interrupting the agent's reasoning loop.
- **Deterministic Scripted Fallback:** If no API keys are provided or all keys are exhausted, the agent operates in **Scripted Mode** (`agent/runner.py`), deterministically generating the verified edits and validations for all canonical scenarios.

---

## 5. Customer Assistant Guardrails & Security

The customer-facing portal (`POST /api/chat`) provides grounded answers directly from `kb_main` with two strict security guardrails:

1. **Passive-Data Boundary:**
   Untrusted user input and knowledge base documents are wrapped inside `<company_knowledge_base>` XML tags with explicit system instructions prohibiting execution of instructions contained within the data.
2. **Citation Whitelist Post-Check:**
   Any citation claimed by the LLM (e.g. `[doc:faq]`) is validated against an exact whitelist of document and fact IDs retrieved from the graph query. Hallucinated or injected citations are stripped before returning to the user.
