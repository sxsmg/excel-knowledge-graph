# src/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

from llama_index.llms.openai import OpenAI
from llama_index.program.openai import OpenAIPydanticProgram
from llama_index.core.prompts.base import ChatPromptTemplate
from llama_index.core.chat_engine.types import ChatMessage

from .config import Settings
from .graph_store import graph_store

# ──────────────────────────────────────────────────────────────
# 1) Our “function‐style” Pydantic schema for any Cypher query
# ──────────────────────────────────────────────────────────────
class CypherQuery(BaseModel):
    """
    A valid Neo4j Cypher statement (read or write).
    """
    cypher: str = Field(..., description="A valid Cypher query")


class Instruction(BaseModel):
    instruction: str


# ──────────────────────────────────────────────────────────────
# 2) Spin up the LLM + Pydantic program for NL→Cypher
# ──────────────────────────────────────────────────────────────
_llm = OpenAI(model="gpt-4", temperature=0)
_prompt = ChatPromptTemplate(
    message_templates=[
        ChatMessage(
            role="system",
            content=(
                "You are a Neo4j expert.  Given a user instruction, "
                "produce ONLY a valid Cypher statement—either a read query "
                "(MATCH/RETURN) or a write operation (CREATE, MERGE, SET, DELETE)."
            ),
        ),
        ChatMessage(role="user", content="{instruction}"),
    ]
)
_program = OpenAIPydanticProgram.from_defaults(
    llm=_llm,
    prompt=_prompt,
    output_cls=CypherQuery,
    verbose=False,
)


# ──────────────────────────────────────────────────────────────
# 3) FastAPI setup
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="Spreadsheet Brain API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# helper to get a neo4j Driver
_settings = Settings()
def _neo4j_driver():
    return GraphDatabase.driver(
        _settings.NEO4J_URI,
        auth=(_settings.NEO4J_USER, _settings.NEO4J_PASSWORD),
    )


@app.get("/labels", response_class=JSONResponse)
def labels():
    """
    Return current node‐labels & relationship‐types for the viewer legend.
    """
    CYPHER = """
      MATCH (n) RETURN DISTINCT labels(n) AS labs
      UNION
      MATCH ()-[r]->() RETURN DISTINCT type(r) AS labs
    """
    nodes, rels = set(), set()
    drv = _neo4j_driver()
    with drv.session(database=_settings.NEO4J_DATABASE) as ses:
        for rec in ses.run(CYPHER):
            v = rec["labs"]
            if isinstance(v, list):
                nodes.update(v)
            else:
                rels.add(v)
    return {"nodeLabels": sorted(nodes), "relTypes": sorted(rels)}


@app.post("/run")
def run_cypher(cmd: Instruction):
    """
    Single “run” endpoint that:
      • NL → Cypher (via our Pydantic program)
      • auto‐detect read vs write
      • execute against Neo4j
      • return { cypher, rows } for reads or { cypher, status } for writes
    """
    # 1) Generate Cypher
    try:
        out: CypherQuery = _program(instruction=cmd.instruction)
    except Exception as e:
        raise HTTPException(400, detail=f"LLM error: {e}")

    cy = out.cypher.strip()
    if not cy:
        raise HTTPException(400, detail="LLM returned empty Cypher")

    head = cy.split(None, 1)[0].upper()
    is_read = head in {"MATCH", "OPTIONAL", "UNWIND", "CALL", "WITH", "RETURN"}

    # 2) Execute
    drv = _neo4j_driver()
    with drv.session(database=_settings.NEO4J_DATABASE) as ses:
        try:
            result = ses.run(cy)
        except Exception as e:
            raise HTTPException(400, detail=f"Cypher failed: {e}")

        if is_read:
            rows = [list(rec.values()) for rec in result]
            return {"cypher": cy, "rows": rows}
        else:
            return {"cypher": cy, "status": "✅ write applied"}
