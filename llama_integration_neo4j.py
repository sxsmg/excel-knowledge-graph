#!/usr/bin/env python3

import logging
from ingest import ingest_xlsx
from llama_index.core import StorageContext, Settings
from llama_index.llms.openai import OpenAI
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core import PropertyGraphIndex
from llama_index.core.graph_stores.types import Relation, EntityNode
from neo4j import GraphDatabase

# ——— Setup logging ——————————————————————————————
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    # 1️⃣ Ingest & parse
    logging.info("➡️ 1) Ingesting Test Sheet 2.xlsx")
    G = ingest_xlsx("Test Sheet 2.xlsx")
    logging.info(f"    • Parsed graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    logging.info(f"    • Sample nodes: {list(G.nodes())[:5]}")
    logging.info(f"    • Sample edges: {list(G.edges())[:5]}")

    # pick a real source so we know there are dependents
    first_src = next(iter(G.edges()))[0]
    logging.info(f"    • Test source cell: {first_src}")

    # 2️⃣ Configure LLM
    Settings.llm = OpenAI(temperature=0, model="gpt-4.1")
    logging.info("➡️ 2) LLM configured (gpt-4.1, temp=0)")

    # 3️⃣ Clear & connect Neo4j
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j","password"))
    with driver.session() as sess:
        sess.run("MATCH (n) DETACH DELETE n")
        logging.info("➡️ 3) Cleared Neo4j DB")
    graph_store = Neo4jPropertyGraphStore(
        url="bolt://localhost:7687",
        username="neo4j",
        password="password",
        database="neo4j"
    )
    StorageContext.from_defaults(graph_store=graph_store)  # not strictly used below
    logging.info("    • Connected to Neo4j at bolt://localhost:7687")

    # 4️⃣ Upsert EntityNode nodes
    logging.info("➡️ 4) Upserting EntityNode nodes")
    cell_nodes = [
        EntityNode(id=addr, name=addr, label="entity", properties={})
        for addr in G.nodes()
    ]
    graph_store.upsert_nodes(cell_nodes)
    with driver.session() as sess:
        cnt = sess.run("MATCH (e:entity) RETURN count(e) AS cnt").single()["cnt"]
    logging.info(f"    • Neo4j now has {cnt} 'entity' nodes")

    # 5️⃣ Upsert DEPENDS_ON relations
    logging.info("➡️ 5) Upserting DEPENDS_ON relations")
    relations = [
        Relation(source_id=src, target_id=dst, label="DEPENDS_ON", properties={})
        for src, dst in G.edges()
    ]
    graph_store.upsert_relations(relations)
    with driver.session() as sess:
        rel_cnt = sess.run("MATCH ()-[r:DEPENDS_ON]->() RETURN count(r) AS cnt")\
                      .single()["cnt"]
        deps = [r["child_name"] for r in sess.run(
            "MATCH (e:entity {name:$name})-[:DEPENDS_ON]->(d) RETURN d.name AS child_name",
            name=first_src
        )]
    logging.info(f"    • Neo4j has {rel_cnt} DEPENDS_ON relationships")
    logging.info(f"    • Raw Cypher deps of {first_src}: {deps}")

    # 6️⃣ Build the PropertyGraphIndex & its query engine
    index = PropertyGraphIndex.from_existing(property_graph_store=graph_store)
    query_engine = index.as_query_engine(
        include_text=False,
        verbose=True,
        graph_schema={
            "node_labels": ["entity"],
            "edge_labels": ["DEPENDS_ON"],
            "node_id_property": "name"
        }
    )
    logging.info("➡️ 6) PropertyGraphIndex query engine ready")

    # 7️⃣ Run our NL impact‐analysis query
    question = f"Which cells break if I change {first_src}?"
    logging.info(f"➡️ 7) Querying KG: {question}")
    resp = query_engine.query(question)
    logging.info("    • Received human‐readable response")

    # 8️⃣ Print the final answer
    print("\n=== FINAL NL→KG RESPONSE ===")
    print(resp)

if __name__ == "__main__":
    main()
