"""
Impact analysis queries for TruthBranch.
"""

# 1. Direct citers
Q_DIRECT_CITERS = """
MATCH (d:Document)-[:CITES]->(f:Fact {id:$old_fact_id})
RETURN d.id AS doc_id, d.title AS title, d.status AS status
"""

# 2. Downstream facts
Q_DOWNSTREAM_FACTS = """
MATCH (g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id})
RETURN DISTINCT g.id AS fact_id, g.key AS key
"""

# 3. Documents citing downstream facts
Q_DOCS_CITING_DOWNSTREAM_FACTS = """
MATCH (d:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id})
RETURN DISTINCT d.id AS doc_id, g.id AS via_fact
"""

# 4. Documents derived from direct citers
Q_MULTI_HOP_DERIVED_DOCS = """
MATCH (d1:Document)-[:CITES]->(f:Fact {id:$old_fact_id})
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1)
RETURN DISTINCT d2.id AS doc_id, d1.id AS via_doc
"""

# 5. Documents derived from documents citing downstream facts
Q_DOCS_DERIVED_FROM_DOWNSTREAM_CITERS = """
MATCH (d1:Document)-[:CITES]->(g:Fact)-[:DERIVED_FROM*1..3]->(f:Fact {id:$old_fact_id})
MATCH (d2:Document)-[:DERIVED_FROM*1..3]->(d1)
RETURN DISTINCT d2.id AS doc_id, d1.id AS via_doc, g.id AS via_fact
"""

# 6. Shortest path from doc to changed fact
Q_SHORTEST_PATH = """
MATCH p = (d2:Document {id:$doc_id})-[:DERIVED_FROM*0..3]->(d1:Document)-[:CITES]->(f:Fact {id:$old_fact_id})
RETURN [n IN nodes(p) | n.id] AS path
ORDER BY length(p) ASC
LIMIT 1
"""

# 7. Document metadata enrichment
Q_DOC_METADATA_BATCH = """
MATCH (d:Document) WHERE d.id IN $doc_ids
OPTIONAL MATCH (d)-[:OWNED_BY]->(p:Person)
OPTIONAL MATCH (d)-[:PUBLISHED_IN]->(s:System)
RETURN d.id AS doc_id, d.title AS title, d.status AS status, d.content AS content,
       p.id AS owner_id, p.name AS owner_name,
       s.id AS system_id, s.name AS system_name
"""
