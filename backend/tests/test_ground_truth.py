"""
Ground-truth tests for TruthBranch (checklist sections 7.7, 7.8, 8.3, 8.4).

Write-first tests: the EXPECTED_* constants below are hard-coded from the checklist and
deliberately NOT derived from data.py, so they can catch mistakes in the dataset itself.

Layer A  (no database)   verifies the dataset + an independent pure-Python oracle.
Layer B  (needs FalkorDB) loads the dataset into scratch graphs and runs the real Cypher
                          from checklist 8.3 / 8.4. Skipped if the DB is unreachable.
Layer C  (contract)      runs your real services once they exist; skipped until then.

Run:   cd backend && pytest -v          (Layer A only)
       docker run --rm -p 6379:6379 falkordb/falkordb && pytest -v   (A + B)
"""
from __future__ import annotations

import os
import re
from collections import deque

import pytest
from dotenv import load_dotenv
load_dotenv()

from app.seed.data import (
    SCENARIOS, build_dataset, expected_edge_count, expected_node_count,
)

# =========================================================================== expected
OLD_FACT = "fact:pricing.pro.monthly@v1"
ANNUAL_FACT = "fact:pricing.pro.annual@v1"
EU_FACT = "fact:pricing.pro.monthly.eu@v1"

# 7.7: exactly these seven documents, with primary reason and shortest "why" path.
EXPECTED_IMPACT = {
    "doc:pricing_page":          ("CITES",            ["doc:pricing_page", OLD_FACT]),
    "doc:sales_deck":            ("CITES",            ["doc:sales_deck", OLD_FACT]),
    "doc:faq":                   ("CITES",            ["doc:faq", OLD_FACT]),
    "doc:revenue_forecast_q4":   ("CITES",            ["doc:revenue_forecast_q4", OLD_FACT]),
    "doc:support_macro_upgrade": ("DERIVED_FROM_DOC", ["doc:support_macro_upgrade", "doc:faq", OLD_FACT]),
    "doc:investor_update":       ("DERIVED_FROM_DOC", ["doc:investor_update", "doc:revenue_forecast_q4", OLD_FACT]),
    "doc:board_deck":            ("DERIVED_FROM_DOC", ["doc:board_deck", "doc:investor_update",
                                                       "doc:revenue_forecast_q4", OLD_FACT]),
}
NEVER_FLAGGED = {"doc:refund_policy", "doc:onboarding_guide", "doc:careers_page", "doc:partner_faq"}
DOWNSTREAM_FACTS = {ANNUAL_FACT}
LITERAL_LEAK_WARN = {"doc:partner_faq"}
OWNERS_TO_NOTIFY = {"p:maya", "p:ravi", "p:sofia", "p:arjun"}           # + p:lena for the WARN

# 7.8 baseline
KEYWORD_49_HITS = {"doc:pricing_page", "doc:sales_deck", "doc:faq", "doc:revenue_forecast_q4",
                   "doc:partner_faq", "doc:careers_page"}
KEYWORD_EXACT_HITS = KEYWORD_49_HITS - {"doc:careers_page"}
KEYWORD_MISSES = {"doc:support_macro_upgrade", "doc:investor_update", "doc:board_deck"}

# 11.6 edit drafting (monthly rule first, then annual rule x10)
EXPECTED_EDITS = {
    "doc:pricing_page": "Lumen Pro costs $59 per month, or $590 per year (two months free). Cancel anytime.",
    "doc:sales_deck": "Slide 7: Lumen Pro at $59/month. Enterprise starts at $149/month with SSO and audit logs.",
    "doc:faq": "How much is Pro? $59 per month. Refunds are available within 30 days of purchase.",
    "doc:revenue_forecast_q4": "Q4 forecast assumes 1,200 Pro seats at $59 per month.",
}
# no literal => cannot be edited deterministically => MARK_STALE (NEEDS_REVIEW)
EXPECTED_MARK_STALE = {"doc:support_macro_upgrade", "doc:investor_update", "doc:board_deck"}


def literal_re(value: int) -> re.Pattern:
    """`$49` but not `$490`, `$149`, `1,$49` or a bare `49` (checklist 8.4 / 11.6)."""
    return re.compile(rf"(?<![\d,])\${value}(?!\d)")


def draft_edit(content: str, old_monthly=49, new_monthly=59) -> str:
    """Reference deterministic replacer. Your real one must produce identical strings."""
    out = literal_re(old_monthly).sub(f"${new_monthly}", content)
    out = literal_re(old_monthly * 10).sub(f"${new_monthly * 10}", out)
    return out


# =========================================================================== oracle
def python_impact(ds: dict, fact_id: str) -> dict:
    """Independent pure-Python impact analysis: shortest path from each document to the
    changed fact through CITES, doc-DERIVED_FROM and fact-DERIVED_FROM edges."""
    nxt: dict[str, list[str]] = {}
    for e in ds["doc_cites"]:
        nxt.setdefault(e["doc"], []).append(e["fact"])
    for e in ds["doc_derived"]:
        nxt.setdefault(e["doc"], []).append(e["from_doc"])
    for e in ds["fact_derived"]:
        nxt.setdefault(e["fact"], []).append(e["from_fact"])

    result = {}
    for d in ds["documents"]:
        start, seen, q, found = d["id"], {d["id"]}, deque([[d["id"]]]), None
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
            if found[1].startswith("fact:") and len(found) == 2:
                reason = "CITES"
            elif found[1].startswith("fact:"):
                reason = "CITES_DERIVED_FACT"
            else:
                reason = "DERIVED_FROM_DOC"
            result[start] = (reason, found)
    return result


# =========================================================================== Layer A
@pytest.fixture(scope="module")
def ds():
    return build_dataset()


@pytest.fixture(scope="module")
def ds_c():
    return build_dataset(with_contradiction=True)


def ids(rows):
    return [r["id"] for r in rows]


def test_counts(ds, ds_c):
    assert (len(ds["people"]), len(ds["systems"]), len(ds["sources"])) == (5, 5, 4)
    assert (len(ds["facts"]), len(ds["documents"])) == (3, 11)
    assert len(ds_c["facts"]) == 4
    assert expected_node_count(ds) == 29 and expected_edge_count(ds) == 41


def test_ids_unique_and_follow_conventions(ds_c):
    patterns = {
        "people": r"^p:[a-z_]+$", "systems": r"^sys:[a-z_]+$", "sources": r"^src:[a-z0-9_]+$",
        "documents": r"^doc:[a-z0-9_]+$", "facts": r"^fact:[a-z0-9_.]+@v\d+$",
    }
    for label, pat in patterns.items():
        got = ids(ds_c[label])
        assert len(got) == len(set(got)), f"duplicate ids in {label}"
        assert all(re.match(pat, i) for i in got), f"bad id in {label}: {got}"


def test_fact_id_matches_key_and_version(ds_c):
    for f in ds_c["facts"]:
        assert f["id"] == f"fact:{f['key']}@v{f['version']}"


def test_active_keys_are_unique(ds_c):
    """The v1 bug: two ACTIVE facts sharing a key made UPDATE_FACT ambiguous."""
    keys = [f["key"] for f in ds_c["facts"] if f["status"] == "ACTIVE"]
    assert len(keys) == len(set(keys))


def test_regional_fact_has_own_key_but_same_subject_and_attribute(ds_c):
    monthly = next(f for f in ds_c["facts"] if f["id"] == OLD_FACT)
    eu = next(f for f in ds_c["facts"] if f["id"] == EU_FACT)
    assert eu["key"] != monthly["key"]
    assert (eu["subject"], eu["attribute"]) == (monthly["subject"], monthly["attribute"])
    assert eu["value"] != monthly["value"]          # => CONTRADICTION is detectable


def test_baseline_has_no_regional_fact(ds):
    assert EU_FACT not in ids(ds["facts"])
    assert all(f["source"] != "src:regional_page_2024" for f in ds["fact_sourced"])


def test_every_edge_endpoint_exists(ds_c):
    node = {k: set(ids(ds_c[k])) for k in ("people", "systems", "sources", "facts", "documents")}
    for e in ds_c["fact_sourced"]:
        assert e["fact"] in node["facts"] and e["source"] in node["sources"]
    for e in ds_c["fact_owned"]:
        assert e["fact"] in node["facts"] and e["person"] in node["people"]
    for e in ds_c["fact_derived"]:
        assert e["fact"] in node["facts"] and e["from_fact"] in node["facts"] and e["rule"]
    for e in ds_c["doc_cites"]:
        assert e["doc"] in node["documents"] and e["fact"] in node["facts"]
    for e in ds_c["doc_derived"]:
        assert e["doc"] in node["documents"] and e["from_doc"] in node["documents"]
    for e in ds_c["doc_published"]:
        assert e["doc"] in node["documents"] and e["system"] in node["systems"]
    for e in ds_c["doc_owned"]:
        assert e["doc"] in node["documents"] and e["person"] in node["people"]


def test_every_document_has_exactly_one_owner_and_system(ds):
    for key in ("doc_owned", "doc_published"):
        docs = [e["doc"] for e in ds[key]]
        assert sorted(docs) == sorted(ids(ds["documents"])), key


def test_every_fact_has_a_source_and_owner(ds):
    assert {e["fact"] for e in ds["fact_sourced"]} == set(ids(ds["facts"]))
    assert {e["fact"] for e in ds["fact_owned"]} == set(ids(ds["facts"]))


def test_no_duplicate_edges(ds_c):
    for key in ("fact_sourced", "fact_owned", "fact_derived", "doc_cites",
                "doc_derived", "doc_published", "doc_owned"):
        pairs = [tuple(sorted(e.items())) for e in ds_c[key]]
        assert len(pairs) == len(set(pairs)), f"parallel duplicate edge in {key}"


def test_document_derivation_is_acyclic(ds):
    nxt = {}
    for e in ds["doc_derived"]:
        nxt.setdefault(e["doc"], []).append(e["from_doc"])

    def has_cycle(n, stack):
        if n in stack:
            return True
        return any(has_cycle(m, stack | {n}) for m in nxt.get(n, []))
    assert not any(has_cycle(d, frozenset()) for d in nxt)


def test_derivation_depth_is_within_the_query_limit(ds):
    """Cypher uses *1..3 for document derivation: the deepest chain must fit."""
    depth = lambda d: 0 if d not in {e["doc"] for e in ds["doc_derived"]} else 1 + max(
        depth(e["from_doc"]) for e in ds["doc_derived"] if e["doc"] == d)
    assert max(depth(d) for d in ids(ds["documents"])) <= 3


def test_annual_fact_is_derived_with_rule_x10(ds):
    assert ds["fact_derived"] == [
        {"fact": ANNUAL_FACT, "from_fact": OLD_FACT, "rule": "x10"}]
    by_id = {f["id"]: f for f in ds["facts"]}
    assert by_id[ANNUAL_FACT]["value"] == 10 * by_id[OLD_FACT]["value"]


def test_distractors_and_dark_dependency_are_wired_as_designed(ds):
    cited = {e["doc"] for e in ds["doc_cites"]}
    derived = {e["doc"] for e in ds["doc_derived"]}
    for d in ("doc:partner_faq", "doc:careers_page"):
        assert d not in cited and d not in derived
    for d in KEYWORD_MISSES:                               # no direct citation of the price
        assert d not in cited
    assert {"doc:refund_policy", "doc:onboarding_guide"} <= cited   # cite refund only


# ------------------------------------------------------------------ oracle vs expected
def test_oracle_finds_exactly_the_expected_documents(ds):
    got = python_impact(ds, OLD_FACT)
    assert set(got) == set(EXPECTED_IMPACT)
    assert not (set(got) & NEVER_FLAGGED)


def test_oracle_reasons_and_paths(ds):
    got = python_impact(ds, OLD_FACT)
    for doc, (reason, path) in EXPECTED_IMPACT.items():
        assert got[doc] == (reason, path), doc


def test_board_deck_is_the_deepest_chain(ds):
    path = python_impact(ds, OLD_FACT)["doc:board_deck"][1]
    assert len(path) == 4


def test_downstream_facts_is_only_the_annual_fact(ds):
    down = {e["fact"] for e in ds["fact_derived"] if e["from_fact"] == OLD_FACT}
    assert down == DOWNSTREAM_FACTS


def test_owners_to_notify(ds):
    owner = {e["doc"]: e["person"] for e in ds["doc_owned"]}
    assert {owner[d] for d in EXPECTED_IMPACT} == OWNERS_TO_NOTIFY
    assert owner[next(iter(LITERAL_LEAK_WARN))] == "p:lena"


def test_changing_an_unrelated_fact_does_not_touch_price_docs(ds):
    got = set(python_impact(ds, "fact:support.refund_days@v1"))
    assert got == {"doc:faq", "doc:support_macro_upgrade", "doc:refund_policy", "doc:onboarding_guide"}


# ------------------------------------------------------------------ baseline 7.8
def test_keyword_baseline(ds):
    naive = {d["id"] for d in ds["documents"] if "49" in d["content"]}
    exact = {d["id"] for d in ds["documents"] if literal_re(49).search(d["content"])}
    assert naive == KEYWORD_49_HITS
    assert exact == KEYWORD_EXACT_HITS
    graph = set(EXPECTED_IMPACT)
    assert graph - exact == KEYWORD_MISSES                  # what keyword search misses
    assert exact - graph == LITERAL_LEAK_WARN               # what only the literal check finds
    assert naive - exact == {"doc:careers_page"}            # naive false positive


# ------------------------------------------------------------------ literal leak 8.4
def test_literal_value_leak_flags_only_partner_faq(ds):
    outside = [d for d in ds["documents"] if d["id"] not in EXPECTED_IMPACT]
    leaks = {d["id"] for d in outside if literal_re(49).search(d["content"])}
    assert leaks == LITERAL_LEAK_WARN


def test_literal_regex_edge_cases():
    r = literal_re(49)
    assert r.search("costs $49 per month") and r.search("$49/month") and r.search("$49.")
    assert not r.search("$490 per year")
    assert not r.search("from $149/month")
    assert not r.search("team of 49 engineers")
    assert not r.search("1,$49")


# ------------------------------------------------------------------ edit drafting 11.6
def test_deterministic_edits(ds):
    docs = {d["id"]: d["content"] for d in ds["documents"]}
    for doc, after in EXPECTED_EDITS.items():
        assert draft_edit(docs[doc]) == after, doc
        assert draft_edit(docs[doc]) != docs[doc]


def test_edit_never_touches_enterprise_price(ds):
    deck = next(d for d in ds["documents"] if d["id"] == "doc:sales_deck")["content"]
    assert "$149/month" in draft_edit(deck)


def test_docs_without_literal_are_left_for_mark_stale(ds):
    docs = {d["id"]: d["content"] for d in ds["documents"]}
    for doc in EXPECTED_MARK_STALE:
        assert draft_edit(docs[doc]) == docs[doc]           # nothing to replace
    assert EXPECTED_MARK_STALE | set(EXPECTED_EDITS) == set(EXPECTED_IMPACT)


# ------------------------------------------------------------------ source rule 7.3 / 10
def test_scenario_sources(ds):
    src = {s["id"]: s for s in ds["sources"]}
    ok = lambda s: s["valid"] and s["trust"] >= 0.6          # SOURCE_INVALID passes when True
    assert ok(src[SCENARIOS["A"]["source_id"]])
    assert not ok(src[SCENARIOS["B"]["source_id"]])
    assert SCENARIOS["C"]["with_contradiction"] is True


def test_contradiction_exists_only_when_flag_is_set(ds, ds_c):
    def clash(d):
        act = [f for f in d["facts"] if f["status"] == "ACTIVE"]
        return {(a["id"], b["id"]) for a in act for b in act
                if a["id"] < b["id"] and a["subject"] == b["subject"]
                and a["attribute"] == b["attribute"] and a["value"] != b["value"]}
    assert clash(ds) == set()
    assert len(clash(ds_c)) == 1


def test_build_dataset_returns_independent_copies():
    a, b = build_dataset(), build_dataset()
    a["documents"][0]["content"] = "mutated"
    assert b["documents"][0]["content"] != "mutated"


# =========================================================================== Layer B
GT_MAIN, GT_C = "kb_gt_main", "kb_gt_contradiction"

# Copy of checklist 8.3 / 8.4. When you write queries/*.py, import these instead.
Q_DIRECT = "MATCH (d:Document)-[:CITES]->(f:Fact {id:$old_fact_id}) RETURN d.id"
Q_DOWNSTREAM = ("MATCH (g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id}) "
                "RETURN DISTINCT g.id")
Q_VIA_FACT = ("MATCH (d:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id}) "
              "RETURN DISTINCT d.id, g.id")
Q_VIA_DOC = ("MATCH (d1:Document)-[:CITES]->(f:Fact {id:$old_fact_id}) "
             "MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1) RETURN DISTINCT d2.id, d1.id")
Q_PATH = ("MATCH p = (d2:Document {id:$doc_id})-[:DERIVED_FROM*0..3]->(d1:Document)"
          "-[:CITES]->(f:Fact {id:$old_fact_id}) RETURN [n IN nodes(p) | n.id] AS path")
Q_CONTRADICTION = ("MATCH (a:Fact {status:'ACTIVE'}), (b:Fact {status:'ACTIVE'}) "
                   "WHERE a.subject = b.subject AND a.attribute = b.attribute "
                   "AND a.id < b.id AND a.value <> b.value RETURN a.id, b.id")
Q_SOURCE = ("MATCH (f:Fact {id:$fact_id}) OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s:Source) "
            "RETURN count(s), collect(s.valid), collect(s.trust)")
Q_LINEAGE_UP = ("MATCH (f:Fact {id:$fact_id})-[:DERIVED_FROM*1..3]->(u:Fact) RETURN DISTINCT u.id")
Q_NODES = "MATCH (n) RETURN count(n)"
Q_EDGES = "MATCH ()-[r]->() RETURN count(r)"

_LOADERS = [
    ("people",    "UNWIND $rows AS x MERGE (n:Person {id:x.id}) "
                  "SET n.name=x.name, n.role=x.role, n.email=x.email"),
    ("systems",   "UNWIND $rows AS x MERGE (n:System {id:x.id}) SET n.name=x.name"),
    ("sources",   "UNWIND $rows AS x MERGE (n:Source {id:x.id}) "
                  "SET n.title=x.title, n.kind=x.kind, n.valid=x.valid, n.trust=x.trust"),
    ("facts",     "UNWIND $rows AS x MERGE (n:Fact {id:x.id}) "
                  "SET n.key=x.key, n.version=x.version, n.subject=x.subject, n.attribute=x.attribute, "
                  "n.value=x.value, n.unit=x.unit, n.status=x.status, n.created_at=x.created_at"),
    ("documents", "UNWIND $rows AS x MERGE (n:Document {id:x.id}) "
                  "SET n.title=x.title, n.kind=x.kind, n.content=x.content, "
                  "n.status=x.status, n.last_reviewed=x.last_reviewed"),
    ("meta",      "UNWIND $rows AS x MERGE (n:Meta {id:x.id}) SET n.revision=x.revision"),
    ("fact_sourced",  "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Source {id:x.source}) "
                      "MERGE (a)-[:SOURCED_FROM]->(b)"),
    ("fact_owned",    "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Person {id:x.person}) "
                      "MERGE (a)-[:OWNED_BY]->(b)"),
    ("fact_derived",  "UNWIND $rows AS x MATCH (a:Fact {id:x.fact}), (b:Fact {id:x.from_fact}) "
                      "MERGE (a)-[r:DERIVED_FROM]->(b) SET r.rule = x.rule"),
    ("doc_cites",     "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Fact {id:x.fact}) "
                      "MERGE (a)-[:CITES]->(b)"),
    ("doc_derived",   "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Document {id:x.from_doc}) "
                      "MERGE (a)-[:DERIVED_FROM]->(b)"),
    ("doc_published", "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:System {id:x.system}) "
                      "MERGE (a)-[:PUBLISHED_IN]->(b)"),
    ("doc_owned",     "UNWIND $rows AS x MATCH (a:Document {id:x.doc}), (b:Person {id:x.person}) "
                      "MERGE (a)-[:OWNED_BY]->(b)"),
]


def load_into(graph, dataset: dict) -> None:
    """Reference seeding (idempotent). seed.py should behave identically."""
    for key, cypher in _LOADERS:
        graph.query(cypher, params={"rows": dataset[key]})
    for label, prop in [("Fact", "id"), ("Fact", "key"), ("Fact", "status"),
                        ("Document", "id"), ("Person", "id"), ("Source", "id"), ("System", "id")]:
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception:
            pass                                             # already indexed


def _connect():
    falkor = pytest.importorskip("falkordb")
    try:
        db = falkor.FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                             port=int(os.getenv("FALKORDB_PORT", "6379")))
        db.list_graphs()
    except Exception as exc:                                  # noqa: BLE001
        pytest.skip(f"FalkorDB not reachable: {exc}")
    return db


def _fresh(db, name, dataset):
    try:
        db.select_graph(name).delete()
    except Exception:
        pass
    g = db.select_graph(name)
    load_into(g, dataset)
    return g


@pytest.fixture(scope="module")
def gmain():
    db = _connect()
    g = _fresh(db, GT_MAIN, build_dataset())
    yield g
    try:
        g.delete()
    except Exception:
        pass


@pytest.fixture(scope="module")
def gc():
    db = _connect()
    g = _fresh(db, GT_C, build_dataset(with_contradiction=True))
    yield g
    try:
        g.delete()
    except Exception:
        pass


def rows(g, q, **params):
    return g.ro_query(q, params=params).result_set


@pytest.mark.db
def test_db_seed_counts(gmain):
    ds = build_dataset()
    assert rows(gmain, Q_NODES)[0][0] == expected_node_count(ds)
    assert rows(gmain, Q_EDGES)[0][0] == expected_edge_count(ds)


@pytest.mark.db
def test_db_seed_is_idempotent():
    db = _connect()
    ds = build_dataset()
    g = _fresh(db, "kb_gt_idem", ds)
    before = (rows(g, Q_NODES)[0][0], rows(g, Q_EDGES)[0][0])
    load_into(g, ds)
    after = (rows(g, Q_NODES)[0][0], rows(g, Q_EDGES)[0][0])
    g.delete()
    assert before == after == (expected_node_count(ds), expected_edge_count(ds))


@pytest.mark.db
def test_db_impact_set_is_exactly_the_expected_seven(gmain):
    direct = {r[0] for r in rows(gmain, Q_DIRECT, old_fact_id=OLD_FACT)}
    via_fact = {r[0] for r in rows(gmain, Q_VIA_FACT, old_fact_id=OLD_FACT)}
    via_doc = {r[0] for r in rows(gmain, Q_VIA_DOC, old_fact_id=OLD_FACT)}
    assert direct == {"doc:pricing_page", "doc:sales_deck", "doc:faq", "doc:revenue_forecast_q4"}
    assert via_fact == {"doc:pricing_page"}
    assert via_doc == {"doc:sales_deck", "doc:support_macro_upgrade",
                       "doc:investor_update", "doc:board_deck"}
    flagged = direct | via_fact | via_doc
    assert flagged == set(EXPECTED_IMPACT)
    assert not (flagged & NEVER_FLAGGED)


@pytest.mark.db
def test_db_downstream_facts(gmain):
    assert {r[0] for r in rows(gmain, Q_DOWNSTREAM, old_fact_id=OLD_FACT)} == DOWNSTREAM_FACTS
    assert {r[0] for r in rows(gmain, Q_LINEAGE_UP, fact_id=ANNUAL_FACT)} == {OLD_FACT}


@pytest.mark.db
@pytest.mark.parametrize("doc", sorted(EXPECTED_IMPACT))
def test_db_why_paths(gmain, doc):
    """Uses *0..3 and [n IN nodes(p) | n.id]: if this fails, see the Python fallback."""
    paths = [r[0] for r in rows(gmain, Q_PATH, doc_id=doc, old_fact_id=OLD_FACT)]
    assert paths, f"no path returned for {doc}"
    assert min(paths, key=len) == EXPECTED_IMPACT[doc][1]


@pytest.mark.db
def test_db_relationship_property_rule(gmain):
    r = rows(gmain, "MATCH (:Fact {id:$a})-[r:DERIVED_FROM]->(:Fact {id:$b}) RETURN r.rule",
             a=ANNUAL_FACT, b=OLD_FACT)
    assert r == [["x10"]]


@pytest.mark.db
def test_db_no_contradiction_in_baseline(gmain):
    assert rows(gmain, Q_CONTRADICTION) == []


@pytest.mark.db
def test_db_contradiction_detected_with_flag(gc):
    got = rows(gc, Q_CONTRADICTION)
    assert len(got) == 1 and set(got[0]) == {OLD_FACT, EU_FACT}


@pytest.mark.db
def test_db_contradiction_flag_does_not_change_impact(gc):
    direct = {r[0] for r in rows(gc, Q_DIRECT, old_fact_id=OLD_FACT)}
    assert direct == {"doc:pricing_page", "doc:sales_deck", "doc:faq", "doc:revenue_forecast_q4"}
    assert rows(gc, Q_DIRECT, old_fact_id=EU_FACT) == []     # nothing cites the regional fact


@pytest.mark.db
def test_db_source_check_rows(gmain):
    n, valid, trust = rows(gmain, Q_SOURCE, fact_id=OLD_FACT)[0]
    assert (n, valid, trust) == (1, [True], [0.95])


@pytest.mark.db
def test_db_main_is_not_modified_by_reads(gmain):
    ds = build_dataset()
    before = rows(gmain, Q_NODES)[0][0], rows(gmain, Q_EDGES)[0][0]
    rows(gmain, Q_DIRECT, old_fact_id=OLD_FACT)
    assert before == (expected_node_count(ds), expected_edge_count(ds))


@pytest.mark.db
def test_db_branch_copy_is_isolated():
    """Mini version of the Day-1 branching spike (checklist 9.3)."""
    db = _connect()
    ds = build_dataset()
    src = _fresh(db, "kb_gt_src", ds)
    branch = None
    try:
        branch = src.copy("kb_gt_branch")
        branch.query("MATCH (f:Fact {id:$id}) SET f.status='SUPERSEDED'", params={"id": OLD_FACT})
        assert rows(branch, "MATCH (f:Fact {id:$id}) RETURN f.status", id=OLD_FACT) == [["SUPERSEDED"]]
        assert rows(src, "MATCH (f:Fact {id:$id}) RETURN f.status", id=OLD_FACT) == [["ACTIVE"]]
        assert rows(src, Q_NODES)[0][0] == expected_node_count(ds)
    finally:
        for g in (branch, src):
            try:
                g.delete()
            except Exception:
                pass


# =========================================================================== Layer C
@pytest.mark.db
def test_contract_impact_for_fact(gmain):
    """Your real service. Expected item shape: {doc_id, reason | reasons, path}."""
    mod = pytest.importorskip("app.services.impact")
    items = mod.impact_for_fact(gmain, OLD_FACT)
    by_doc = {i["doc_id"]: i for i in items}
    assert set(by_doc) == set(EXPECTED_IMPACT)
    for doc, (reason, path) in EXPECTED_IMPACT.items():
        item = by_doc[doc]
        reasons = item.get("reasons") or [item["reason"]]
        assert reason in reasons, doc
        assert item["path"] == path, doc


def test_contract_keyword_baseline():
    mod = pytest.importorskip("app.services.baseline")
    ds = build_dataset()
    result = mod.keyword_baseline(ds["documents"], "49") if hasattr(mod, "keyword_baseline") else None
    if result is None:
        pytest.skip("baseline.keyword_baseline(documents, literal) not implemented yet")
    assert set(result) == KEYWORD_49_HITS