"""
Lineage and fact queries for TruthBranch.
"""

Q_LINEAGE_SUPERSEDES = """
MATCH (f:Fact {id:$fact_id})-[:SUPERSEDES*0..10]->(old:Fact)
RETURN old.id AS id, old.version AS version, old.value AS value, old.status AS status
ORDER BY old.version DESC
"""

Q_LINEAGE_SOURCES = """
MATCH (f:Fact {id:$fact_id})-[:SOURCED_FROM]->(s:Source)
RETURN s.id AS id, s.title AS title, s.valid AS valid, s.trust AS trust
"""

Q_LINEAGE_UPSTREAM = """
MATCH (f:Fact {id:$fact_id})-[:DERIVED_FROM*1..3]->(u:Fact)
RETURN DISTINCT u.id AS id, u.value AS value
"""

Q_FACT_BY_ID = """
MATCH (f:Fact {id:$fact_id})
RETURN f.id AS id, f.key AS key, f.version AS version, f.value AS value, f.unit AS unit, f.status AS status
"""

Q_ACTIVE_FACT_BY_KEY = """
MATCH (f:Fact {key:$key, status:'ACTIVE'})
RETURN f.id AS id, f.key AS key, f.version AS version, f.value AS value, f.unit AS unit, f.status AS status
"""
