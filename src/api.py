# src/api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .query_engine import ask_question
from .graph_store import driver, Settings as _S
from .patches import clean_cypher
from llama_index.core.indices.property_graph import TextToCypherRetriever
from .graph_store import graph_store
from .llm import llm

app = FastAPI(title="Spreadsheet Brain API")

# allow our viewer (3000) → API (8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ImpactRequest(BaseModel):
    cell: str

class AskPayload(BaseModel):
    question: str

class UpdatePayload(BaseModel):
    question: str


@app.post("/impact")
def impact(req: ImpactRequest):
    cy = """
    MATCH (s:entity {name:$cell})
    MATCH (s)-[:DEPENDS_ON*1..]->(d:entity)
    RETURN DISTINCT d.name AS dep
    """
    with driver().session(database=_S().NEO4J_DATABASE) as ses:
        deps = [r["dep"] for r in ses.run(cy, cell=req.cell)]
    return {"source": req.cell, "dependents": deps}


@app.post("/ask")
@app.post("/v1/ask")
def ask(payload: AskPayload):
    try:
        return ask_question(payload.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update")
def update_graph(payload: UpdatePayload):
    """
    NL → Cypher → write transaction → return confirmation
    """
    retriever = TextToCypherRetriever(
        graph_store,
        llm=llm,
        text_to_cypher_template=graph_store.text_to_cypher_template,
    )
    # pick the right method
    if hasattr(retriever, "generate_cypher"):
        raw = retriever.generate_cypher(payload.question)
    else:
        raw = retriever.to_cypher({"query_str": payload.question})
    cypher = clean_cypher(str(raw))

    head = cypher.split(None, 1)[0].upper()
    if head not in {"CREATE", "MERGE", "DELETE", "SET"}:
        raise HTTPException(400, detail=f"LLM did not produce a write statement:\n{cypher}")

    with driver().session(database=_S().NEO4J_DATABASE) as ses:
        ses.run(cypher)

    return {"answer": "Graph updated", "cypher": cypher}


@app.get("/labels", response_class=JSONResponse)
def labels():
    """
    Return existing node‐labels & relationship‐types for the viewer legend.
    """
    CYPHER = """
    MATCH (n)            RETURN DISTINCT labels(n) AS labs
    UNION
    MATCH ()-[r]->()     RETURN DISTINCT type(r)  AS labs
    """
    nodes, rels = set(), set()
    with driver().session(database=_S().NEO4J_DATABASE) as ses:
        for rec in ses.run(CYPHER):
            labs = rec["labs"]
            if isinstance(labs, list):
                nodes.update(labs)
            else:
                rels.add(labs)
    return {"nodeLabels": sorted(nodes), "relTypes": sorted(rels)}
