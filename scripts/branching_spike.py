"""
Branching Spike for TruthBranch (Checklist Section 9.3 / Block 1.4)
Answers the four existential questions regarding FalkorDB graph copy.
"""
import time
from falkordb import FalkorDB
from backend.app.config import get_settings

def run_spike():
    settings = get_settings()
    db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)
    
    print("=" * 60)
    print("TRUTHBRANCH BRANCHING SPIKE")
    print(f"Connecting to FalkorDB at {settings.falkordb_host}:{settings.falkordb_port}")
    print("=" * 60)

    # Ensure kb_main exists
    main_graph = db.select_graph("kb_main")
    main_nodes_init = main_graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    main_edges_init = main_graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    print(f"1. Initial kb_main: {main_nodes_init} nodes, {main_edges_init} edges")

    branch_name = "kb_cr_test_spike"
    try:
        db.select_graph(branch_name).delete()
    except Exception:
        pass

    # Question 1: Does GRAPH.COPY work via client.copy()?
    t0 = time.time()
    try:
        branch = main_graph.copy(branch_name)
        copy_time = (time.time() - t0) * 1000
        q1_success = True
        print(f"2. Q1 - GRAPH.COPY '{branch_name}': SUCCESS in {copy_time:.2f} ms")
    except Exception as e:
        q1_success = False
        print(f"2. Q1 - GRAPH.COPY FAILED: {e}")
        return

    # Question 2: Is writing to the branch isolated from kb_main?
    print("3. Q2 - Testing Mutation Isolation:")
    branch.query("CREATE (:Person {id:'p:ghost', name:'Ghost User'})")
    branch.query("MATCH (f:Fact {id:'fact:pricing.pro.monthly@v1'}) SET f.value = 999, f.status = 'SUPERSEDED'")
    
    branch_nodes = branch.query("MATCH (n) RETURN count(n)").result_set[0][0]
    main_nodes_after = main_graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    main_fact_val = main_graph.query("MATCH (f:Fact {id:'fact:pricing.pro.monthly@v1'}) RETURN f.value, f.status").result_set[0]
    
    q2_success = (
        main_nodes_after == main_nodes_init and 
        branch_nodes == main_nodes_init + 1 and 
        main_fact_val == [49, "ACTIVE"]
    )
    print(f"   Branch nodes: {branch_nodes} (expected {main_nodes_init + 1})")
    print(f"   Main nodes: {main_nodes_after} (expected {main_nodes_init})")
    print(f"   Main fact untouched: value={main_fact_val[0]}, status='{main_fact_val[1]}'")
    print(f"   Q2 Result: {'PASSED (Zero leakage)' if q2_success else 'FAILED'}")

    # Question 3: Are indexes preserved on the branch copy?
    print("4. Q3 - Testing Index Retention on Branch:")
    # In FalkorDB, we can test by calling an index-related query or re-creating it
    # If the attribute is already indexed, FalkorDB raises: Attribute 'id' is already indexed
    try:
        branch.query("CREATE INDEX FOR (f:Fact) ON (f.id)")
        q3_preserved = False
        print("   Index had to be created (was not cloned)")
    except Exception as e:
        if "already indexed" in str(e).lower():
            q3_preserved = True
            print(f"   Index verified cloned: '{e}'")
        else:
            q3_preserved = False
            print(f"   Index check returned: {e}")
    print(f"   Q3 Result: {'CONFIRMED CLONED' if q3_preserved else 'MANUAL SEED NEEDED'}")

    # Question 4: Does branch deletion leave kb_main intact?
    print("5. Q4 - Testing Branch Deletion:")
    branch.delete()
    remaining_graphs = db.list_graphs()
    main_nodes_final = main_graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
    main_edges_final = main_graph.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    
    q4_success = (
        branch_name not in remaining_graphs and
        main_nodes_final == main_nodes_init and
        main_edges_final == main_edges_init
    )
    print(f"   Branch deleted from server: {branch_name not in remaining_graphs}")
    print(f"   Main graph unchanged: {main_nodes_final} nodes, {main_edges_final} edges")
    print(f"   Q4 Result: {'PASSED' if q4_success else 'FAILED'}")

    print("=" * 60)
    print(f"OVERALL SPIKE DECISION: {'OPTION A (GRAPH.COPY) VERIFIED' if (q1_success and q2_success and q4_success) else 'FALLBACK TO OPTION B'}")
    print("=" * 60)

if __name__ == "__main__":
    run_spike()
