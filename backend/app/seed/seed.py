"""
Seeding logic for TruthBranch.
Loads the Lumen Analytics dataset into FalkorDB with idempotent UNWIND + MERGE queries.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from falkordb import FalkorDB, Graph

from backend.app.config import get_settings
from backend.app.db import get_falkordb
from backend.app.seed.data import (
    build_dataset,
    expected_edge_count,
    expected_node_count,
)

INDEXES = [
    "CREATE INDEX FOR (f:Fact) ON (f.id)",
    "CREATE INDEX FOR (f:Fact) ON (f.key)",
    "CREATE INDEX FOR (f:Fact) ON (f.status)",
    "CREATE INDEX FOR (d:Document) ON (d.id)",
    "CREATE INDEX FOR (p:Person) ON (p.id)",
    "CREATE INDEX FOR (s:Source) ON (s.id)",
    "CREATE INDEX FOR (s:System) ON (s.id)",
]


def create_indexes(graph: Graph) -> None:
    for idx_stmt in INDEXES:
        try:
            graph.query(idx_stmt)
        except Exception as e:
            # Attribute already indexed is fine
            if "already indexed" not in str(e).lower():
                print(f"Warning on index: {idx_stmt} -> {e}", file=sys.stderr)


def seed_graph(
    graph_name: str = "kb_main",
    with_contradiction: bool = False,
    drop_existing: bool = True,
    client: FalkorDB | None = None,
) -> dict[str, Any]:
    """Seed the given graph with the Lumen Analytics dataset."""
    if client is None:
        client = get_falkordb()

    if drop_existing:
        try:
            client.select_graph(graph_name).delete()
        except Exception:
            pass

    graph = client.select_graph(graph_name)
    ds = build_dataset(with_contradiction=with_contradiction)

    # 1. Nodes
    graph.query(
        """
        UNWIND $people AS x
        MERGE (p:Person {id: x.id})
        SET p.name = x.name, p.role = x.role, p.email = x.email
        """,
        params={"people": ds["people"]},
    )

    graph.query(
        """
        UNWIND $systems AS x
        MERGE (s:System {id: x.id})
        SET s.name = x.name
        """,
        params={"systems": ds["systems"]},
    )

    graph.query(
        """
        UNWIND $sources AS x
        MERGE (s:Source {id: x.id})
        SET s.title = x.title, s.kind = x.kind, s.valid = x.valid, s.trust = x.trust
        """,
        params={"sources": ds["sources"]},
    )

    graph.query(
        """
        UNWIND $facts AS x
        MERGE (f:Fact {id: x.id})
        SET f.key = x.key, f.version = x.version, f.subject = x.subject,
            f.attribute = x.attribute, f.value = x.value, f.unit = x.unit,
            f.status = x.status, f.created_at = x.created_at
        """,
        params={"facts": ds["facts"]},
    )

    graph.query(
        """
        UNWIND $documents AS x
        MERGE (d:Document {id: x.id})
        SET d.title = x.title, d.kind = x.kind, d.status = x.status,
            d.last_reviewed = x.last_reviewed, d.content = x.content
        """,
        params={"documents": ds["documents"]},
    )

    graph.query(
        """
        UNWIND $meta AS x
        MERGE (m:Meta {id: x.id})
        SET m.revision = x.revision
        """,
        params={"meta": ds["meta"]},
    )

    # 2. Relationships
    graph.query(
        """
        UNWIND $fact_sourced AS x
        MATCH (f:Fact {id: x.fact}), (s:Source {id: x.source})
        MERGE (f)-[:SOURCED_FROM]->(s)
        """,
        params={"fact_sourced": ds["fact_sourced"]},
    )

    graph.query(
        """
        UNWIND $fact_owned AS x
        MATCH (f:Fact {id: x.fact}), (p:Person {id: x.person})
        MERGE (f)-[:OWNED_BY]->(p)
        """,
        params={"fact_owned": ds["fact_owned"]},
    )

    graph.query(
        """
        UNWIND $fact_derived AS x
        MATCH (f:Fact {id: x.fact}), (base:Fact {id: x.from_fact})
        MERGE (f)-[r:DERIVED_FROM]->(base)
        SET r.rule = x.rule
        """,
        params={"fact_derived": ds["fact_derived"]},
    )

    graph.query(
        """
        UNWIND $doc_cites AS x
        MATCH (d:Document {id: x.doc}), (f:Fact {id: x.fact})
        MERGE (d)-[:CITES]->(f)
        """,
        params={"doc_cites": ds["doc_cites"]},
    )

    graph.query(
        """
        UNWIND $doc_derived AS x
        MATCH (d:Document {id: x.doc}), (parent:Document {id: x.from_doc})
        MERGE (d)-[:DERIVED_FROM]->(parent)
        """,
        params={"doc_derived": ds["doc_derived"]},
    )

    graph.query(
        """
        UNWIND $doc_published AS x
        MATCH (d:Document {id: x.doc}), (s:System {id: x.system})
        MERGE (d)-[:PUBLISHED_IN]->(s)
        """,
        params={"doc_published": ds["doc_published"]},
    )

    graph.query(
        """
        UNWIND $doc_owned AS x
        MATCH (d:Document {id: x.doc}), (p:Person {id: x.person})
        MERGE (d)-[:OWNED_BY]->(p)
        """,
        params={"doc_owned": ds["doc_owned"]},
    )

    # 3. Create Indexes
    create_indexes(graph)

    # Count nodes & edges
    node_res = graph.query("MATCH (n) RETURN count(n) AS cnt")
    node_count = node_res.result_set[0][0]

    edge_res = graph.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
    edge_count = edge_res.result_set[0][0]

    return {
        "graph_name": graph_name,
        "nodes": node_count,
        "edges": edge_count,
        "expected_nodes": expected_node_count(ds),
        "expected_edges": expected_edge_count(ds),
        "with_contradiction": with_contradiction,
    }


def reset(client: FalkorDB | None = None) -> dict[str, Any]:
    """Wipes and reseeds the authoritative kb_main graph cleanly."""
    return seed_graph(graph_name="kb_main", with_contradiction=False, drop_existing=True, client=client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TruthBranch knowledge graph")
    parser.add_argument("--graph", default="kb_main", help="Graph container name")
    parser.add_argument("--with-contradiction", action="store_true", help="Include regional conflicting fact")
    parser.add_argument("--no-drop", action="store_true", help="Do not drop graph before seeding (test idempotency)")
    args = parser.parse_args()

    res = seed_graph(
        graph_name=args.graph,
        with_contradiction=args.with_contradiction,
        drop_existing=not args.no_drop,
    )
    print(f"Seeded '{res['graph_name']}': {res['nodes']} nodes (expected {res['expected_nodes']}), "
          f"{res['edges']} edges (expected {res['expected_edges']})")
