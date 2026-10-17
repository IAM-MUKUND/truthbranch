# Next Steps: Sprint 3 (Agent First, Interface Second)

Sprint 1 (Foundation & Ground Truth) and Sprint 2 (Change Engine, Diff, Checks, Lifecycle, Merge) are 100% complete with 70/70 passing tests.

### Immediate Next Tasks (Sprint 3 Start):
1. **Block 3.1: Tool Layer for Agent (75 min)**
   - Expose backend services as standardized agent tools with JSON schemas and Pydantic argument validators in `backend/app/agent/tools.py`:
     - `get_lineage(fact_id)`
     - `get_impact(cr_id)`
     - `run_checks(cr_id)`
     - `propose_edits_for_affected_docs(cr_id)`
     - `request_verification(cr_id, reason, person_id)`
     - `submit_for_approval(cr_id)`
   - Hard limits: enforce that the agent has NO merge tool and NO approve tool.
2. **Block 3.2: Groq Agent Loop (90 min)**
   - Implement `backend/app/agent/loop.py` using Groq tool calling (`llama-3.3-70b-versatile`, `temperature=0`, step cap=8).
   - Implement system prompt and prompt templates in `backend/app/agent/prompts.py`.
   - Implement fallback `AGENT_MODE=scripted` in `backend/app/agent/scripted.py`.
3. **Block 3.3: Agent Review Endpoint (30 min)**
   - Expose `POST /api/change-requests/{id}/agent-review` returning the agent timeline and decision report.
4. **Block 3.4 & 3.5: React Frontend (150 min)**
   - Initialize Vite + React review interface with change card, impact table, baseline card, checks panel, agent timeline, diff viewer, and approval action bar.
