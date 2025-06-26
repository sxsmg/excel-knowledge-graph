# src/query_engine.py

from functools import lru_cache
import re

from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import TextToCypherRetriever

from .graph_store import graph_store
from .llm import llm
from .patches import clean_cypher

# Pre‐compile our “break impact” pattern:
_BREAK_RE = re.compile(r"which cells break if i change\s+([\w!]+)\?", re.IGNORECASE)

@lru_cache(maxsize=1)
def _index() -> PropertyGraphIndex:
    return PropertyGraphIndex.from_existing(property_graph_store=graph_store)

@lru_cache(maxsize=1)
def _make_retriever():
    return TextToCypherRetriever(
        graph_store,
        llm=llm,
        text_to_cypher_template=graph_store.text_to_cypher_template,
        response_template="{query}"
    )

def ask_question(question: str) -> dict:
    """
    Try matching our “Which cells break if I change X?” pattern first,
    and run a pure‐Cypher lookup.  Otherwise, fall back to LLM→Cypher.
    """
    m = _BREAK_RE.match(question.strip())
    if m:
        cell = m.group(1)
        # run direct Cypher for dependents:
        from .graph_store import driver, Settings as _S
        cy = """
        MATCH (s:entity {name:$cell})
        MATCH (s)-[:DEPENDS_ON*1..]->(d:entity)
        RETURN DISTINCT d.name AS dep
        """
        with driver().session(database=_S().NEO4J_DATABASE) as ses:
            deps = [r["dep"] for r in ses.run(cy, cell=cell)]
        ans = f"Cells {', '.join(deps) or '—none—'} would break if you change {cell}."
        return {"question": question, "answer": ans}

    # otherwise, let Llama‐Index generate a Cypher query,
    # clean off any ``` fences, and execute it for us too:
    retriever = _make_retriever()
    # depending on Llama‐Index version:
    if hasattr(retriever, "generate_cypher"):
        raw = retriever.generate_cypher(question)
    else:
        raw = retriever.to_cypher({"query_str": question})
    cypher = clean_cypher(str(raw))

    # if it's a read‐only Cypher, run it:
    if cypher.upper().startswith("MATCH"):
        from .graph_store import driver, Settings as _S
        with driver().session(database=_S().NEO4J_DATABASE) as ses:
            result = ses.run(cypher)
            rows = [record.values() for record in result]
        ans = {"cypher": cypher, "rows": rows}
        return {"question": question, "answer": ans}

    # else, just return the generated Cypher:
    return {"question": question, "answer": {"cypher": cypher}}
