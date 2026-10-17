# TruthBranch — Git for Company Knowledge

> **A knowledge change is proposed on a branch, investigated through the graph, validated, drafted into follow-up edits by an agent, approved by a human, and merged with history preserved.**

Built for Hackathon Tracks:
- **Track 1:** Agents That Act on Connected Data
- **Track 3:** Company Brain

---

## 1. Quick Start

### Prerequisites
- Python 3.11+
- Docker (for FalkorDB)
- Node.js & npm (for React UI in Sprint 3)

### Running FalkorDB
```bash
docker run -d --name truthbranch-falkordb -p 6380:6379 -p 3000:3000 falkordb/falkordb:latest
```

### Backend Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Run Tests
```bash
pytest backend/tests/test_ground_truth.py -v
```

### Run Backend API
```bash
uvicorn backend.app.main:app --reload --port 8000
```
