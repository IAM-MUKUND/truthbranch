# Next Steps: Sprint 4 (Reliability, Documentation & Submission)

Sprint 1 (Foundation & Ground Truth), Sprint 2 (Change Engine, Diff, Checks, Lifecycle, Merge), and Sprint 3 (Autonomous Agent Loop, Tool Layer & Interactive Frontend) are **100% complete with 77/77 passing tests**.

### Status Overview
- **Backend API**: Running on port `8000` with 11 endpoints.
- **FalkorDB**: Running on port `6380`.
- **Groq LLM**: `openai/gpt-oss-120b` (heavy reasoning/tools) + `openai/gpt-oss-20b` (light reports).
- **Frontend SPA**: React 18 + Vite 5 + TypeScript in `frontend/`, builds cleanly with 0 errors.
- **Custom Datasets**: Dynamic fact lookup and dynamic citation repointing enabled.

### Upcoming Sprint 4 Tasks:
1. **Block 4.1: Failure-Case & Invariant Tests**
   - Assert `kb_main` snapshot is byte-for-byte identical before approval.
   - Test duplicate ops and idempotent re-merge.
   - Test merge conflict when `base_revision` moves.
2. **Block 4.2: Clean-Room Environment Verification**
   - Run verification script to confirm zero undocumented dependencies.
3. **Block 4.3: Documentation & Architecture Diagrams**
   - Finalize `README.md`, `docs/architecture.md`, `docs/graph-schema.md`, `docs/cypher-queries.md`.
4. **Block 4.4 & 4.5: Submission Preparation**
   - Demo video script and walkthrough guide.
