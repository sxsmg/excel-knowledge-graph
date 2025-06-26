# src/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

from llama_index.llms.openai import OpenAI
from llama_index.program.openai import OpenAIPydanticProgram
from llama_index.core.prompts.base import ChatPromptTemplate
from llama_index.core.chat_engine.types import ChatMessage

from .config import Settings
from .graph_store import graph_store
from pyvis.network import Network

import networkx as nx
import asyncio

from fastapi.staticfiles import StaticFiles
from pathlib import Path


update_listeners = []

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
                 "Your graph models every spreadsheet cell as a node labeled `entity` "
                     "and every formula dependency as `DEPENDS_ON`, where\n"
                     "  (A)-[:DEPENDS_ON]->(B)  means  B depends on A.\n\n"
                     "When generating Cypher:\n"
                     " • Never use the internal id() function—always match on the `name` property.\n"
                     " • For read queries use  MATCH … RETURN.\n"
                     " • For updates use  MATCH … SET …  and traverse in the correct direction:\n"
                     "     ‘cells dependent on X’ →  MATCH (x:entity {name:X})-[:DEPENDS_ON]->(d:entity)\n"
                     "     then  SET d.<prop> = <value>.\n\n"
                     "Produce ONLY the final Cypher."
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

    upper = cy.upper()
    is_read = (
        not any(w in upper for w in (" SET ", " CREATE ", " MERGE ", " DELETE "))
        and upper.split(None, 1)[0] in {"MATCH", "OPTIONAL", "UNWIND", "CALL", "WITH", "RETURN"}
    )
    # 2) Execute
    drv = _neo4j_driver()
    with drv.session(database=_settings.NEO4J_DATABASE) as ses:
        try:
            result = ses.run(cy)
        except Exception as e:
            raise HTTPException(400, detail=f"Cypher failed: {e}")

        if is_read:
            rows = [list(rec.values()) for rec in result]
            response = {"cypher": cy, "rows": rows}
            print('response', response)
            return response 
        else:
            print(f"📣 Broadcasting reload to {len(update_listeners)} listener(s)")
            for q in update_listeners:
                try:
                    q.put_nowait("reload")
                except Exception as e:
                    print("❌ Failed to notify a listener:", e)
            return {"cypher": cy, "status": "✅ write applied"}


@app.get("/events")
async def events():
    async def event_stream():
        print("👂  New SSE client connecting… currently", len(update_listeners), "listeners")
        q = asyncio.Queue()
        update_listeners.append(q)
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            update_listeners.remove(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/notify_update")
def notify_update():
    print("📣 Emitting reload to", len(update_listeners), "listeners")
    for q in update_listeners:
        q.put_nowait("reload")
    return {"ok": True}

@app.get("/graph", response_class=HTMLResponse)
def graph_view():
    """
    Render the full spreadsheet‐brain dependency graph as a pyvis HTML page.
    """
    # 1) Pull every dependency from Neo4j
    CYPHER = """
    MATCH (n:entity)-[r:DEPENDS_ON]->(m:entity)
    RETURN n.name AS source, m.name AS target
    """
    G = nx.DiGraph()
    with _neo4j_driver().session(database=_settings.NEO4J_DATABASE) as ses:
        for rec in ses.run(CYPHER):
            src = rec["source"]
            dst = rec["target"]
            # add nodes (pyvis will dedupe), and an edge
            G.add_node(src, title=src)
            G.add_node(dst, title=dst)
            G.add_edge(src, dst)

    # 2) Build the pyvis network
    net = Network(
        height="750px",
        width="100%",
        directed=True,
        notebook=False,
        bgcolor="#ffffff",
        font_color="#000000",
    )
    net.from_nx(G)

    # Optional: tweak defaults for all nodes
    for node in net.nodes:
        node["size"]  = 20
        node["label"] = node["id"]
        node["title"] = node["id"]

    # 3) Render straight to HTML and return
    html = net.generate_html()
    html = (
        html
        .replace(
            '<link rel="stylesheet" href="/lib/vis-network.min.css">',
            '<link rel="stylesheet" '
            'href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.css">'
        )
        .replace(
            '<script src="/lib/vis-network.min.js"></script>',
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.js"></script>'
        )
        # PyVis inlines its utils.js in the HTML already; if it still emits a /lib binding:
        .replace('<script src="/lib/bindings/utils.js"></script>', '')
    )
    tool_ui = """
      <div style="padding:8px; background:#fafafa; border-bottom:1px solid #ddd;">
        <input id="query" placeholder="Enter question or update…" style="width:60%;padding:6px" />
        <button id="runBtn" style="padding:6px 12px">Run</button>
        <span id="status" style="margin-left:8px;color:#555"></span>
      </div>
      <script>
        // NL → /run
        document.getElementById("runBtn").onclick = async () => {
          const q = document.getElementById("query").value.trim();
          if (!q) return;
          document.getElementById("status").textContent = "⏳ running…";
          const res = await fetch("/run", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({instruction: q})
          });
          const j = await res.json();
          document.getElementById("status").textContent =
            j.rows ? "✅ done" : (j.status || "✅ write applied");
        };

        // SSE reload on external updates or writes
        const es = new EventSource("/events");
        es.onmessage = () => {
          console.log("⚡️ reload event, refreshing graph");
          window.location.reload();
        };
      </script>
    """

    # insert the toolbar right after <body>
    html = html.replace("<body>", "<body>" + tool_ui)
    print("final HTML", html)
    return HTMLResponse(html)