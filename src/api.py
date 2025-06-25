from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .ingest import build_nx_graph
from .graph_store import upsert_graph
from .llm import llm
from llama_index.core import PropertyGraphIndex
from .query_engine import ask_question 

app = FastAPI(title="Spreadsheet Brain API")


class ImpactRequest(BaseModel):
    cell: str


class AskPayload(BaseModel):
    question: str


@app.post("/impact")
def impact(req: ImpactRequest):
    # query via pure Cypher – keeps it deterministic
    from .graph_store import driver, Settings as _S
    q = """
    MATCH (s:entity {name:$cell})
    MATCH (s)-[:DEPENDS_ON*1..]->(d) RETURN DISTINCT d.name AS dep
    """
    with driver().session(database=_S().NEO4J_DATABASE) as ses:
        deps = [r["dep"] for r in ses.run(q, cell=req.cell)]
    return {"source": req.cell, "dependents": deps}


@app.post("/v1/ask")
@app.post("/ask")                # 👈 NEW alias
def ask(payload: AskPayload):
    try:
        return ask_question(payload.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
