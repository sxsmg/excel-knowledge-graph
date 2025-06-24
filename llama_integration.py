#!/usr/bin/env python3
# llama_integration.py

import sys
import logging
import json
from ingest import ingest_xlsx
from neo4j import GraphDatabase
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.graph_stores.types import EntityNode, Relation

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

def main(path: str):
    # 1️⃣ Ingest & parse
    logging.info(f"➡️ Ingesting {path}")
    G = ingest_xlsx(path)
    first_src = next(iter(G.edges()))[0]
    logging.info(f"    • Parsed graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    logging.info(f"    • Example edge: {first_src} → {next(iter(G.successors(first_src)))}")

    # 2️⃣ Clear Neo4j
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    with driver.session() as sess:
        sess.run("MATCH (n) DETACH DELETE n")
    logging.info("➡️ Cleared Neo4j database")

    # 3️⃣ Upsert into Neo4j
    store = Neo4jPropertyGraphStore(
        url="bolt://localhost:7687",   # url
        username="neo4j",                   # username
        password="password",                # password
        database="neo4j"                    # database
    )
    # nodes
    store.upsert_nodes([
        EntityNode(id=addr, name=addr, label="entity", properties={})
        for addr in G.nodes()
    ])
    # edges
    store.upsert_relations([
        Relation(source_id=s, target_id=t, label="DEPENDS_ON", properties={})
        for s, t in G.edges()
    ])
    logging.info(f"➡️ Upserted {G.number_of_nodes()} nodes & {G.number_of_edges()} dependencies")

    # 4️⃣ Multi-hop Cypher
    cypher = """
    MATCH (start:entity {name:$name})
    MATCH (start)-[:DEPENDS_ON*1..]->(d:entity)
    RETURN DISTINCT d.name AS dependent
    """
    with driver.session() as sess:
        deps = [r["dependent"] for r in sess.run(cypher, name=first_src)]

    # 5️⃣ Emit JSON
    print(json.dumps({"source": first_src, "dependents": deps}))

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("Usage: python llama_integration.py <path_to_xlsx>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
