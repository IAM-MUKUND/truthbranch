"""
Validation check queries for TruthBranch.
"""

Q_CHECK_SOURCE = """
MATCH (f:Fact {id:$fact_id})
OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s:Source)
RETURN f.id AS fact_id, count(s) AS source_count, collect(s.valid) AS valid_flags, collect(s.trust) AS trust_scores
"""

# Uses a.id < b.id to match the test suite and prevent duplicate pairs
Q_CHECK_CONTRADICTION = """
MATCH (a:Fact {status:'ACTIVE'}), (b:Fact {status:'ACTIVE'})
WHERE a.subject = b.subject AND a.attribute = b.attribute AND a.id < b.id AND a.value <> b.value
RETURN a.id AS id1, a.value AS val1, b.id AS id2, b.value AS val2
"""

Q_ALL_DOCUMENTS = """
MATCH (d:Document)
RETURN d.id AS doc_id, d.title AS title, d.content AS content
"""
