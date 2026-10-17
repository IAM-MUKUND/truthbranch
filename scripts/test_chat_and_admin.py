import httpx

client = httpx.Client(base_url="http://localhost:8000", timeout=20.0)

# Reset first to clean baseline
print("[1] Resetting demo baseline...")
client.post("/api/admin/reset-demo", json={"with_contradiction": False})

print("[2] Fetching entities from GET /api/entities...")
r_ent = client.get("/api/entities")
assert r_ent.status_code == 200
ent = r_ent.json()
print("    People count:", len(ent["people"]))
print("    Facts count: ", len(ent["facts"]))
print("    Sources count:", len(ent["sources"]))

print("\n[3] Customer asks AI at /: 'How much is the Pro plan?'")
r_chat1 = client.post("/api/chat", json={"messages": [{"role": "user", "content": "How much is the Pro plan?"}]})
assert r_chat1.status_code == 200
chat1 = r_chat1.json()
print("    AI Response Before Merge:\n    ", chat1["content"])
print("    Citations:", chat1["citations"])
assert "$49" in chat1["content"] or "49" in chat1["content"]

print("\n[4] Admin creates CR on /admin using entities dropdown...")
proposer = ent["people"][0]["name"]
r_cr = client.post("/api/change-requests", json={
    "title": "Live Truth Demo Price Increase",
    "fact_key": "pricing.pro.monthly",
    "new_value": 59,
    "source_id": "src:pricing_committee_memo_2026_10",
    "created_by": proposer,
})
assert r_cr.status_code == 200
cr_id = r_cr.json()["id"]
print("    Created CR:", cr_id)

print("\n[5] Running Agent Review on isolated branch...")
r_rev = client.post(f"/api/change-requests/{cr_id}/agent-review")
assert r_rev.status_code == 200
rev = r_rev.json()
print("    Agent Verdict:", rev["verdict"])
print("    Steps count:  ", len(rev["steps"]))

print("\n[6] Human Approves and Merges to kb_main...")
r_app = client.post(f"/api/change-requests/{cr_id}/approve", json={"reviewer": "Board Chair"})
assert r_app.status_code == 200
r_merge = client.post(f"/api/change-requests/{cr_id}/merge")
assert r_merge.status_code == 200
print("    Merged successfully! Revision:", r_merge.json()["revision"])

print("\n[7] Customer asks AI at /: 'What is the Pro plan price now?'")
r_chat2 = client.post("/api/chat", json={"messages": [{"role": "user", "content": "What is the Pro plan price now?"}]})
assert r_chat2.status_code == 200
chat2 = r_chat2.json()
print("    AI Response After Merge:\n    ", chat2["content"])
print("    Citations:", chat2["citations"])
assert "$59" in chat2["content"] or "59" in chat2["content"]

print("\n" + "=" * 70)
print("SUCCESS: LIVE TRUTH PROPAGATION VERIFIED END-TO-END!")
print("=" * 70)
