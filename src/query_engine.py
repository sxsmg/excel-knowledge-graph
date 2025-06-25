# src/query_engine.py
"""
A very thin “smart-question” layer on top of the existing Neo4j graph store.
"""

from functools import lru_cache
from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import TextToCypherRetriever
from .llm import llm

from .config import Settings
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

_cfg = Settings()

print("LLM API KEY", _cfg.LLM_API_KEY)

graph_store = Neo4jPropertyGraphStore(
    url=_cfg.NEO4J_URI,
    username=_cfg.NEO4J_USER,
    password=_cfg.NEO4J_PASSWORD,
    database=_cfg.NEO4J_DATABASE,
)

@lru_cache(maxsize=1)
def _index() -> PropertyGraphIndex:
    """Wrap the current Neo4j store exactly once."""
    return PropertyGraphIndex.from_existing(property_graph_store=graph_store)


@lru_cache(maxsize=1)
def _query_engine():
    """Build a retriever+engine (cached)."""
    cypher_retriever = TextToCypherRetriever(
        graph_store,
        llm=llm,
        text_to_cypher_template=graph_store.text_to_cypher_template,
        response_template=("Generated Cypher:\n{query}\n\n"
                           "Results:\n{response}"),
    )
    return _index().as_query_engine(
        include_text=False,
        verbose=False,
        sub_retrievers=[cypher_retriever],
    )


# --------------------------------------------------------------------------- #
#  Public helper imported by api.py
# --------------------------------------------------------------------------- #
def ask_question(question: str) -> dict:
    """
    Free-form QA entry point used by /v1/ask.

    Parameters
    ----------
    question : str
        Natural-language prompt, e.g. “Which cells break if I change Sales!C2?”

    Returns
    -------
    dict
        {"question": ..., "answer": ...}
    """
    engine = _query_engine()
    answer = engine.query(question)
    return {
        "question": question,
        "answer": str(answer).strip(),
    }
