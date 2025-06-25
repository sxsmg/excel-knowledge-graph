#!/usr/bin/env python3
import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ingest import ingest_xlsx
from neo4j import GraphDatabase
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.graph_stores.types import EntityNode, Relation

# ——— Load .env ——————————————————————————————
load_dotenv()

# ——— CLI args ——————————————————————————————
p = argparse.ArgumentParser(
    description="Watch a spreadsheet and sync to Neo4j on changes."
)
p.add_argument("xlsx_path", help="Path to the .xlsx file to watch")
p.add_argument(
    "--uri",
    default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    help="Neo4j Bolt URI",
)
p.add_argument(
    "--user",
    default=os.getenv("NEO4J_USER", "neo4j"),
    help="Neo4j username",
)
p.add_argument(
    "--password",
    default=os.getenv("NEO4J_PASSWORD", "password"),
    help="Neo4j password",
)
p.add_argument(
    "--database",
    default=os.getenv("NEO4J_DATABASE", "neo4j"),
    help="Neo4j database name",
)
args = p.parse_args()

XLSX_PATH      = args.xlsx_path
NEO4J_URI      = args.uri
NEO4J_USER     = args.user
NEO4J_PASSWORD = args.password
NEO4J_DATABASE = args.database

# ——— Logging ——————————————————————————————
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# sanity checks
if not os.path.isfile(XLSX_PATH):
    logging.error(f"❌ File not found: {XLSX_PATH}")
    sys.exit(1)

def sync_to_neo4j(path: str):
    logging.info(f"🔄 Re-ingesting `{path}`…")
    G = ingest_xlsx(path)
    logging.info(f"    • Parsed graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # 1) clear
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as sess:
        sess.run("MATCH (n) DETACH DELETE n")

    # 2) upsert into graph store
    store = Neo4jPropertyGraphStore(
        url=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )
    nodes = [
        EntityNode(id=addr, name=addr, label="entity", properties={})
        for addr in G.nodes()
    ]
    store.upsert_nodes(nodes)

    rels = [
        Relation(source_id=s, target_id=t, label="DEPENDS_ON", properties={})
        for s, t in G.edges()
    ]
    store.upsert_relations(rels)

    logging.info("✅ Neo4j updated with new dependency graph")

class XlsxHandler(FileSystemEventHandler):
    def __init__(self, watch_file):
        super().__init__()
        self.watch_file = os.path.abspath(watch_file)

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == self.watch_file:
            logging.info(f"📄 Detected change in {event.src_path}")
            time.sleep(0.5)  # debounce
            sync_to_neo4j(event.src_path)

if __name__ == "__main__":
    watch_dir = os.path.dirname(os.path.abspath(XLSX_PATH)) or "."
    handler = XlsxHandler(XLSX_PATH)
    observer = Observer()
    observer.schedule(handler, path=watch_dir, recursive=False)

    logging.info(f"🚀 Watching `{XLSX_PATH}` for changes…")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

