# llama_integration.py
# llama_integration.py

from ingest import ingest_xlsx
from llama_index.core import StorageContext, Settings
from llama_index.llms.openai import OpenAI
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.knowledge_graph.base import KnowledgeGraphIndex
from llama_index.core.query_engine.knowledge_graph_query_engine import KnowledgeGraphQueryEngine

# 0) Build the dependency graph from your workbook
#    Replace the path with whichever sheet you want to ingest.
G = ingest_xlsx("Test Sheet 2.xlsx")

# 1) Configure your LLM
Settings.llm = OpenAI(temperature=0, model="gpt-3.5-turbo")

# 2) Connect to Neo4j (or switch to Nebula as you prefer)
graph_store = Neo4jPropertyGraphStore(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your_password",
    database="neo4j"
)

storage_context = StorageContext.from_defaults(graph_store=graph_store)

# 3) Create the KnowledgeGraphIndex
kg_index = KnowledgeGraphIndex(
    storage_context=storage_context,
    graph_store=graph_store
)

# 4) Upsert every edge in G as a triplet
for src, dst in G.edges():
    # (subject, predicate, object)
    kg_index.upsert_triplet((src, "DEPENDS_ON", dst))

# 5) Spin up the NL→Graph query engine
query_engine = KnowledgeGraphQueryEngine(
    storage_context=storage_context,
    llm=Settings.llm,
    verbose=True
)

# 6) Try a query!
resp = query_engine.query("Which cells break if I change Sheet1!A5?")
print(resp)
