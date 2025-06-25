#!/usr/bin/env python3

import logging
import json
from ingest import ingest_xlsx
from neo4j import GraphDatabase
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.graph_stores.types import EntityNode, Relation

# ——— Setup logging ——————————————————————————————
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

def main():
    # 1️⃣ Ingest & parse all sheets & ranges
    logging.info("➡️ Ingesting Test Sheet 2.xlsx")
    G = ingest_xlsx("Test Sheet 2.xlsx")
    sheets = sorted({ addr.split("!")[0] for addr in G.nodes() })
    logging.info(f"    • Sheets seen in graph: {sheets}")
    logging.info(f"    • Parsed graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # pick a real source for our demo
    first_src = next(iter(G.edges()))[0]
    logging.info(f"    • Example edge: {first_src} → {next(iter(G.successors(first_src)))}")

    # 2️⃣ Connect & clear Neo4j
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","password"))
    with driver.session() as sess:
        sess.run("MATCH (n) DETACH DELETE n")
    logging.info("➡️ Cleared Neo4j database")

    # 3️⃣ Upsert nodes & edges
    graph_store = Neo4jPropertyGraphStore(
        url="bolt://localhost:7687",
        username="neo4j",
        password="password",
        database="neo4j"
    )
    # nodes
    nodes = [ EntityNode(id=addr, name=addr, label="entity", properties={})
              for addr in G.nodes() ]
    graph_store.upsert_nodes(nodes)
    # edges
    rels = [ Relation(source_id=s, target_id=t, label="DEPENDS_ON", properties={})
             for s,t in G.edges() ]
    graph_store.upsert_relations(rels)
    logging.info(f"➡️ Upserted {len(nodes)} nodes & {len(rels)} DEPENDS_ON relations")

    # 4️⃣ Run a multi‐hop Cypher to get *all* dependents
    multi_hop_query = """
    MATCH (start:entity {name:$name})
    MATCH (start)-[:DEPENDS_ON*1..]->(d:entity)
    RETURN DISTINCT d.name AS dependent
    """
    with driver.session() as sess:
        result = sess.run(multi_hop_query, name=first_src)
        dependents = [ record["dependent"] for record in result ]

    # 5️⃣ Output JSON
    print(json.dumps(dependents))

if __name__ == "__main__":
    main()
