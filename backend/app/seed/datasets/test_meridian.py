"""
Ground-truth tests for the large 'Meridian Systems' dataset.

Layer A (no DB): structural invariants + an independent pure-Python oracle + frozen
                 scenario numbers.
Layer B (needs FalkorDB, auto-skipped): for EVERY fact, the Cypher impact set (checklist 8.3
                 queries 1, 3, 4) must equal the oracle's impact set.

Run: cd backend && pytest tests/test_meridian_dataset.py -v
"""
from __future__ import annotations

import os
import re
from collections import Counter, deque

import pytest

try:                                            # repo layout: backend.app...
    from backend.app.seed.datasets import meridian as M
except ImportError:                             # plain: app...
    from app.seed.datasets import meridian as M

LIT = M.LITERALS


def lit_re(literal: str) -> re.Pattern:
    return re.compile(r"(?<![\d,])" + re.escape(literal) + r"(?!\d)")


# =========================================================================== oracle
def oracle(ds: dict, fact_id: str) -> dict:
    """doc_id -> shortest node path to fact_id (CITES, doc DERIVED_FROM, fact DERIVED_FROM)."""
    nxt: dict[str, list[str]] = {}
    for e in ds["doc_cites"]:
        nxt.setdefault(e["doc"], []).append(e["fact"])
    for e in ds["doc_derived"]:
        nxt.setdefault(e["doc"], []).append(e["from_doc"])
    for e in ds["fact_derived"]:
        nxt.setdefault(e["fact"], []).append(e["from_fact"])
    out = {}
    for d in ds["documents"]:
        seen, q, found = {d["id"]}, deque([[d["id"]]]), None
        while q:
            path = q.popleft()
            if path[-1] == fact_id and len(path) > 1:
                found = path
                break
            for n in nxt.get(path[-1], []):
                if n not in seen:
                    seen.add(n)
                    q.append(path + [n])
        if found:
            out[d["id"]] = found
    return out


@pytest.fixture(scope="module")
def ds():
    return M.build_dataset()


@pytest.fixture(scope="module")
def ds_c():
    return M.build_dataset(with_contradiction=True)


def ids(rows):
    return [r["id"] for r in rows]


# =========================================================================== Layer A
def test_size_is_large_and_broad(ds):
    assert len(ds["facts"]) >= 100 and len(ds["documents"]) >= 380
    assert len(ds["people"]) >= 30 and len(ds["systems"]) >= 12 and len(ds["sources"]) >= 20
    assert {f["key"].split(".")[0] for f in ds["facts"]} >= {
        "pricing", "support", "sla", "hr", "comp", "finance", "security", "privacy",
        "legal", "client", "eng", "it", "sales", "partner", "company"}


def test_ids_unique_and_well_formed(ds_c):
    pats = {"people": r"^p:[a-z]+$", "systems": r"^sys:[a-z_]+$", "sources": r"^src:[a-z0-9_]+$",
            "documents": r"^doc:[a-z0-9_]+$", "facts": r"^fact:[a-z0-9_.]+@v\d+$"}
    for label, pat in pats.items():
        got = ids(ds_c[label])
        assert len(got) == len(set(got)), label
        assert all(re.match(pat, i) for i in got), label


def test_active_keys_unique_and_ids_match_keys(ds_c):
    keys = [f["key"] for f in ds_c["facts"] if f["status"] == "ACTIVE"]
    assert len(keys) == len(set(keys))
    assert all(f["id"] == f"fact:{f['key']}@v{f['version']}" for f in ds_c["facts"])


def test_all_edges_reference_existing_nodes(ds_c):
    n = {k: set(ids(ds_c[k])) for k in ("people", "systems", "sources", "facts", "documents")}
    for e in ds_c["fact_sourced"]: assert e["fact"] in n["facts"] and e["source"] in n["sources"]
    for e in ds_c["fact_owned"]: assert e["fact"] in n["facts"] and e["person"] in n["people"]
    for e in ds_c["fact_derived"]: assert e["fact"] in n["facts"] and e["from_fact"] in n["facts"]
    for e in ds_c["doc_cites"]: assert e["doc"] in n["documents"] and e["fact"] in n["facts"]
    for e in ds_c["doc_derived"]: assert e["doc"] in n["documents"] and e["from_doc"] in n["documents"]
    for e in ds_c["doc_published"]: assert e["doc"] in n["documents"] and e["system"] in n["systems"]
    for e in ds_c["doc_owned"]: assert e["doc"] in n["documents"] and e["person"] in n["people"]


def test_ownership_cardinality(ds):
    all_docs = sorted(ids(ds["documents"]))
    assert sorted(e["doc"] for e in ds["doc_owned"]) == all_docs
    assert sorted(e["doc"] for e in ds["doc_published"]) == all_docs
    all_facts = sorted(ids(ds["facts"]))
    assert sorted(e["fact"] for e in ds["fact_sourced"]) == all_facts
    assert sorted(e["fact"] for e in ds["fact_owned"]) == all_facts


def test_no_duplicate_edges(ds_c):
    for k in M.__dict__.get("_EDGE_KEYS", ("fact_sourced", "fact_owned", "fact_derived", "doc_cites",
                                           "doc_derived", "doc_published", "doc_owned")):
        pairs = [tuple(sorted(e.items())) for e in ds_c[k]]
        assert len(pairs) == len(set(pairs)), k


def test_every_person_owns_something(ds):
    owners = {e["person"] for e in ds["doc_owned"]} | {e["person"] for e in ds["fact_owned"]}
    assert set(ids(ds["people"])) <= owners


def test_rendered_literals_are_unique_across_facts():
    dup = [k for k, c in Counter(LIT.values()).items() if c > 1]
    assert not dup, dup


def test_derived_values_follow_their_rule(ds):
    val = {f["id"]: f["value"] for f in ds["facts"]}
    assert len(ds["fact_derived"]) == 3
    for e in ds["fact_derived"]:
        mult = int(e["rule"].lstrip("x"))
        assert val[e["fact"]] == val[e["from_fact"]] * mult, e


def test_literal_hits_equal_citers_plus_annotated_dark_docs(ds):
    cit = {}
    for e in ds["doc_cites"]:
        cit.setdefault(e["fact"], set()).add(e["doc"])
    for f in ds["facts"]:
        hits = {d["id"] for d in ds["documents"] if lit_re(LIT[f["key"]]).search(d["content"])}
        expected = cit.get(f["id"], set()) | set(M.DARK_DEPENDENCIES.get(f["id"], []))
        assert hits == expected, f["id"]


def test_near_miss_and_unrelated_docs_match_no_literal(ds):
    plain = {d["id"]: d["content"] for d in ds["documents"]
             if d["id"] in set(M.NEAR_MISS_DOCS) | set(M.UNRELATED_DOCS)}
    assert len(plain) == len(M.NEAR_MISS_DOCS) + len(M.UNRELATED_DOCS)
    for did, text in plain.items():
        for key, literal in LIT.items():
            assert not lit_re(literal).search(text), (did, key)


def test_near_miss_docs_do_contain_tempting_digits(ds):
    text = {d["id"]: d["content"] for d in ds["documents"]}
    assert "79" in text["doc:careers_page"] and "149" in text["doc:customers_page"]
    assert "72" in text["doc:status_history_blog"]


def test_derivation_graphs_are_acyclic_and_shallow(ds):
    def depth(edges, key_from, key_to):
        nxt = {}
        for e in edges:
            nxt.setdefault(e[key_from], []).append(e[key_to])
        memo = {}

        def d(n, stack=()):
            assert n not in stack, f"cycle at {n}"
            if n not in memo:
                memo[n] = 0 if n not in nxt else 1 + max(d(m, stack + (n,)) for m in nxt[n])
            return memo[n]
        return max((d(n) for n in list(nxt)), default=0)
    assert depth(ds["doc_derived"], "doc", "from_doc") <= 3
    assert depth(ds["fact_derived"], "fact", "from_fact") <= 3


def test_derived_fact_only_citers_have_no_derived_children(ds):
    """Keeps the *1..3 Cypher impact queries complete (checklist 8.3 note)."""
    derived_facts = {e["fact"] for e in ds["fact_derived"]}
    cites = {}
    for e in ds["doc_cites"]:
        cites.setdefault(e["doc"], set()).add(e["fact"])
    parents = {e["from_doc"] for e in ds["doc_derived"]}
    for doc, fs in cites.items():
        if fs <= derived_facts:
            assert doc not in parents, doc


def test_orphan_facts_have_no_documents_and_no_impact(ds):
    cited = {e["fact"] for e in ds["doc_cites"]}
    for fid in M.ORPHAN_FACTS:
        assert fid not in cited
        assert oracle(ds, fid) == {}
        key = fid[len("fact:"):-len("@v1")]
        assert not any(lit_re(LIT[key]).search(d["content"]) for d in ds["documents"])


def test_dataset_is_deterministic():
    a, b = M.build_dataset(), M.build_dataset()
    assert a == b
    a["documents"][0]["content"] = "mutated"
    assert M.build_dataset()["documents"][0]["content"] != "mutated"


# ------------------------------------------------------------------ scenarios (frozen)
#            scenario: (impacted docs, distinct owners, dark-dependency leaks)
FROZEN = {"A": (30, 11, 4), "B": (11, 5, 1), "C": (30, 11, 4), "D": (16, 5, 1),
          "E": (4, 1, 1), "F": (6, 2, 0), "G": (0, 0, 0), "H": (9, 4, 1)}


@pytest.mark.parametrize("sc", sorted(FROZEN))
def test_scenario_impact_matches_frozen_ground_truth(ds, sc):
    spec = M.SCENARIOS[sc]
    fid = f"fact:{spec['fact_key']}@v1"
    imp = oracle(ds, fid)
    own = {e["doc"]: e["person"] for e in ds["doc_owned"]}
    hits = {d["id"] for d in ds["documents"] if lit_re(LIT[spec["fact_key"]]).search(d["content"])}
    assert (len(imp), len({own[d] for d in imp}), len(hits - set(imp))) == FROZEN[sc]
    assert all(len(p) <= 5 for p in imp.values())          # <= 3 doc hops + cite


def test_hero_scenario_has_wide_blast_radius_and_deep_paths(ds):
    imp = oracle(ds, "fact:pricing.business.monthly@v1")
    assert 25 <= len(imp) <= 40
    assert imp["doc:board_appendix_pack"] == [
        "doc:board_appendix_pack", "doc:board_deck", "doc:investor_update",
        "doc:revenue_forecast", "fact:pricing.business.monthly@v1"]
    assert imp["doc:sales_enablement_quiz"][-1] == "fact:pricing.business.monthly@v1"
    assert not {"doc:careers_page", "doc:customers_page", "doc:refund_policy_page"} & set(imp)


def test_hero_keyword_baseline(ds):
    imp = set(oracle(ds, "fact:pricing.business.monthly@v1"))
    naive = {d["id"] for d in ds["documents"] if "79" in d["content"]}
    exact = {d["id"] for d in ds["documents"] if lit_re("$79").search(d["content"])}
    assert (len(naive), len(exact), len(imp)) == (20, 19, 30)
    assert naive - exact == {"doc:careers_page"}                  # naive false positive
    assert len(imp - exact) == 15                                 # keyword search misses half
    assert exact - imp == set(M.DARK_DEPENDENCIES["fact:pricing.business.monthly@v1"])


def test_derived_fact_propagation_in_hero_and_hr(ds):
    down = lambda base: {e["fact"] for e in ds["fact_derived"] if e["from_fact"] == base}
    assert down("fact:pricing.business.monthly@v1") == {"fact:pricing.business.annual@v1"}
    assert down("fact:hr.pto.annual_days@v1") == {"fact:hr.pto.max_balance_days@v1"}


def test_scenario_definitions_are_valid(ds):
    facts = {f["key"]: f for f in ds["facts"]}
    src = {s["id"]: s for s in ds["sources"]}
    ok = lambda s: s["valid"] and s["trust"] >= 0.6
    for sc, spec in M.SCENARIOS.items():
        assert spec["fact_key"] in facts and spec["source_id"] in src, sc
        assert spec["new_value"] != facts[spec["fact_key"]]["value"], sc
    assert all(ok(src[M.SCENARIOS[k]["source_id"]]) for k in "ADEFG")
    assert not ok(src[M.SCENARIOS["B"]["source_id"]])
    assert not ok(src[M.SCENARIOS["H"]["source_id"]])


def test_contradiction_only_with_flag(ds, ds_c):
    def clash(d):
        act = [f for f in d["facts"] if f["status"] == "ACTIVE"]
        return {(a["id"], b["id"]) for a in act for b in act if a["id"] < b["id"]
                and a["subject"] == b["subject"] and a["attribute"] == b["attribute"]
                and a["value"] != b["value"]}
    assert clash(ds) == set()
    assert len(clash(ds_c)) == 1
    assert M.SCENARIOS["C"]["with_contradiction"] and len(ds_c["facts"]) == len(ds["facts"]) + 1


# =========================================================================== Layer B
Q_DIRECT = "MATCH (d:Document)-[:CITES]->(f:Fact {id:$f}) RETURN d.id"
Q_VIA_FACT = ("MATCH (d:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$f}) "
              "RETURN DISTINCT d.id")
Q_VIA_DOC = ("MATCH (d1:Document)-[:CITES]->(f:Fact {id:$f}) "
             "MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1) RETURN DISTINCT d2.id")
Q_CONTRA = ("MATCH (a:Fact {status:'ACTIVE'}), (b:Fact {status:'ACTIVE'}) "
            "WHERE a.subject = b.subject AND a.attribute = b.attribute AND a.id < b.id "
            "AND a.value <> b.value RETURN a.id, b.id")
Q_NODES, Q_EDGES = "MATCH (n) RETURN count(n)", "MATCH ()-[r]->() RETURN count(r)"
_LOADERS = [
    ("people", "UNWIND $rows AS x MERGE (n:Person {id:x.id}) SET n.name=x.name, n.role=x.role, n.email=x.email"),
    ("systems", "UNWIND $rows AS x MERGE (n:System {id:x.id}) SET n.name=x.name"),
    ("sources", "UNWIND $rows AS x MERGE (n:Source {id:x.id}) SET n.title=x.title, n.kind=x.kind, n.valid=x.valid, n.trust=x.trust"),
    ("facts", "UNWIND $rows AS x MERGE (n:Fact {id:x.id}) SET n.key=x.key, n.version=x.version, n.subject=x.subject, n.attribute=x.attribute, n.value=x.value, n.unit=x.unit, n.status=x.status, n.created_at=x.created_at"),
    ("documents", "UNWIND $rows AS x MERGE (n:Document {id:x.id}) SET n.title=x.title, n.kind=x.kind, n.content=x.content, n.status=x.status, n.last_reviewed=x.last_reviewed"),
    ("meta", "UNWIND $rows AS x MERGE (n:Meta {id:x.id}) SET n.revision=x.revision"),
    ("fact_sourced", "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Source {id:x.source}) MERGE (a)-[:SOURCED_FROM]->(b)"),
    ("fact_owned", "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Person {id:x.person}) MERGE (a)-[:OWNED_BY]->(b)"),
    ("fact_derived", "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Fact {id:x.from_fact}) MERGE (a)-[r:DERIVED_FROM]->(b) SET r.rule=x.rule"),
    ("doc_cites", "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Fact {id:x.fact}) MERGE (a)-[:CITES]->(b)"),
    ("doc_derived", "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Document {id:x.from_doc}) MERGE (a)-[:DERIVED_FROM]->(b)"),
    ("doc_published", "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:System {id:x.system}) MERGE (a)-[:PUBLISHED_IN]->(b)"),
    ("doc_owned", "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Person {id:x.person}) MERGE (a)-[:OWNED_BY]->(b)"),
]


def _db():
    falkor = pytest.importorskip("falkordb")
    try:
        db = falkor.FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                             port=int(os.getenv("FALKORDB_PORT", "6379")))
        db.list_graphs()
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"FalkorDB not reachable: {exc}")
    return db


def _load(db, name, dataset):
    try:
        db.select_graph(name).delete()
    except Exception:
        pass
    g = db.select_graph(name)
    for key, cypher in _LOADERS:
        g.query(cypher, params={"rows": dataset[key]})
    for label, prop in [("Fact", "id"), ("Fact", "key"), ("Document", "id")]:
        try:
            g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception:
            pass
    return g


@pytest.fixture(scope="module")
def g(ds):
    graph = _load(_db(), "kb_meridian_test", ds)
    yield graph
    graph.delete()


def rows(graph, q, **p):
    return graph.ro_query(q, params=p).result_set


@pytest.mark.db
def test_db_counts_match_dataset(g, ds):
    nodes = sum(len(ds[k]) for k in ("people", "systems", "sources", "facts", "documents", "meta"))
    edges = sum(len(ds[k]) for k in ("fact_sourced", "fact_owned", "fact_derived", "doc_cites",
                                     "doc_derived", "doc_published", "doc_owned"))
    assert rows(g, Q_NODES)[0][0] == nodes and rows(g, Q_EDGES)[0][0] == edges


@pytest.mark.db
def test_db_impact_equals_oracle_for_every_fact(g, ds):
    """The headline claim: Cypher == independent oracle for all facts."""
    for f in ds["facts"]:
        fid = f["id"]
        cypher = ({r[0] for r in rows(g, Q_DIRECT, f=fid)} | {r[0] for r in rows(g, Q_VIA_FACT, f=fid)}
                  | {r[0] for r in rows(g, Q_VIA_DOC, f=fid)})
        assert cypher == set(oracle(ds, fid)), fid


@pytest.mark.db
def test_db_hero_numbers(g):
    fid = "fact:pricing.business.monthly@v1"
    direct = {r[0] for r in rows(g, Q_DIRECT, f=fid)}
    via_doc = {r[0] for r in rows(g, Q_VIA_DOC, f=fid)}
    assert len(direct | via_doc | {r[0] for r in rows(g, Q_VIA_FACT, f=fid)}) == 30
    assert "doc:board_appendix_pack" in via_doc


@pytest.mark.db
def test_db_orphan_facts_flag_nothing(g):
    for fid in M.ORPHAN_FACTS:
        assert rows(g, Q_DIRECT, f=fid) == [] and rows(g, Q_VIA_DOC, f=fid) == []


@pytest.mark.db
def test_db_contradiction_toggle(ds_c):
    db = _db()
    base = _load(db, "kb_meridian_nocontra", M.build_dataset())
    flagged = _load(db, "kb_meridian_contra", ds_c)
    try:
        assert rows(base, Q_CONTRA) == []
        got = rows(flagged, Q_CONTRA)
        assert len(got) == 1 and set(got[0]) == {"fact:pricing.business.monthly@v1",
                                                  "fact:pricing.business.monthly.eu@v1"}
    finally:
        base.delete()
        flagged.delete()