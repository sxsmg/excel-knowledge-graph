from neo4j import GraphDatabase
from .config import Settings
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.graph_stores.types import EntityNode, Relation

_cfg = Settings()  # singleton


# --------------------------------------------------------------------------- #
graph_store = Neo4jPropertyGraphStore(
    url=_cfg.NEO4J_URI,
    username=_cfg.NEO4J_USER,
    password=_cfg.NEO4J_PASSWORD,
    database=_cfg.NEO4J_DATABASE,
)

def driver():
    return GraphDatabase.driver(
        _cfg.NEO4J_URI,
        auth=(_cfg.NEO4J_USER, _cfg.NEO4J_PASSWORD)
    )


def clear_db():
    with driver().session(database=_cfg.NEO4J_DATABASE) as sess:
        sess.run("MATCH (n) DETACH DELETE n")


def store_for_llama():
    return graph_store 


def upsert_graph(nx_graph):
    gs = store_for_llama()
    nodes = [EntityNode(id=n, name=n, label="entity") for n in nx_graph.nodes()]
    rels  = [
        Relation(source_id=s, target_id=t, label="DEPENDS_ON")
        for s, t in nx_graph.edges()
    ]
    gs.upsert_nodes(nodes)
    gs.upsert_relations(rels)
    return gs
