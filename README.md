# Spreadsheet Brain Prototype

A Python-and-FastAPI based “Spreadsheet Brain” that:

- **Ingests** Excel files into a Neo4j property graph  
- **Exposes** a natural-language → Cypher API backed by an LLM (via llama-index)  
- **Serves** an integrated, single-page PyVis UI at `/graph` with:
  - **Dynamic reads** (highlights matching nodes in yellow)  
  - **Persistent writes** (sets node `color` props in Neo4j and auto-reloads)  
  - **Server-Sent Events** for live reload on external changes  

---

## 📦 Repo Layout

```

spreadsheet\_ai\_parser/
├── src/
│   ├── api.py             # FastAPI app + LLM integration + PyVis UI
│   ├── cli.py             # `load`, `watch`, `api` commands
│   ├── ingest.py          # parse .xlsx → NetworkX graph
│   ├── parser.py          # formula dependency extractor
│   ├── graph\_store.py     # Neo4jPropertyGraphStore wrapper
│   ├── sync\_watch.py      # XLSX file watcher → upsert → SSE
│   ├── query\_engine.py    # optional NL→Cypher engine for CLI use
│   ├── config.py          # environment settings (.env via python-dotenv)
│   └── patches.py         # Cypher cleanup helpers
├── requirements.txt       # Python deps (FastAPI, neo4j, llama-index, pyvis, etc.)
└── README.md              # **YOU ARE HERE**

````

---

## 🔧 Setup

1. **Neo4j**  
   - Run a local Neo4j instance (e.g. Docker or desktop)  
   - Create a database named `neo4j` (or set `NEO4J_DATABASE`)

2. **Environment**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r src/requirements.txt
```

3. **Configure**
   Create a `.env` in the project root:

   ```ini
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=neo4j

   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o
   LLM_API_KEY=your_openai_key
   ```

---

## 🚀 CLI Commands

From the project root, with your venv active:

| Command                                    | What it does                                    |
| ------------------------------------------ | ----------------------------------------------- |
| `python -m src.cli load path/to/file.xlsx` | One-shot: parse & push graph into Neo4j         |
| `python -m src.cli watch file.xlsx`        | Watch XLSX for edits, auto-sync & broadcast SSE |
| `python -m src.cli api`                    | Launch FastAPI server (default: `:8000`)        |

---

## 🌐 HTTP API

Once `python -m src.cli api` is running:

* **GET** `/labels`
  Returns

  ```json
  {
    "nodeLabels":["entity"],
    "relTypes":["DEPENDS_ON"]
  }
  ```

* **POST** `/run`
  Natural-language → Cypher → execute.

  ```jsonc
  // request
  { "instruction": "Which cells break if I change Sheet1!A2?" }
  // response (read)
  {
    "cypher":"MATCH (n:entity {name:'Sheet1!A2'})-[:DEPENDS_ON]->(d:entity) RETURN d.name",
    "rows":[ ["Sheet1!B2"], ["Sheet1!C2"] ]
  }
  // response (write)
  {
    "cypher":"MATCH (x:entity {name:'A2'})-[:DEPENDS_ON]->(d:entity) SET d.color='red'",
    "status":"✅ write applied"
  }
  ```

* **GET** `/events`
  Server-Sent Events stream (`text/event-stream`) that emits `data: reload` on:

  * any `/run` write, or
  * any file-watcher upsert (`sync_watch.py` → `/notify_update`)

* **POST** `/notify_update`
  Trigger a `reload` event manually (used by the watcher).

---

## 🖥️ Integrated UI

Point your browser at:

```
http://localhost:8000/graph
```

You’ll see:

1. **Full dependency graph** drawn with \[PyVis/vis-network]
2. **Toolbar** at the top:

   * **Input box** for plain-English queries/updates
   * **Run** button:

     * **Reads** highlight returned cells in yellow (no reload)
     * **Writes** persist `color` in Neo4j and auto-reload via SSE
   * **Status** message
3. **Live-reload**: on any write or external XLSX change, the graph auto-refreshes to pick up persisted colors.

---

## 🔍 Example Queries

### Read-only (yellow highlights)

* `Which cells break if I change Sales!C2?`
* `List all cells that Sales!E2 depends on.`
* `Show me all cells two steps away from Inventory!B3.`
* `Show me all leaf cells (no dependents).`

### Write-through (persistent colors + reload)

* `Set color to red for all cells dependent on Sales!C2.`
* `Set color to blue for all mutual-dependency cycles.`
* `Remove the color property from every cell.`

### Combined

* `Find all cells that depend on Marketing!D5 and set their color to orange.`

---

## ⚙️ Architecture Overview

```text
┌─────────────┐       ┌────────────────┐       ┌───────────┐
│  Excel/XLSX │  →    │ ingest_xlsx()  │  →    │  networkx │
└─────────────┘       └────────────────┘       └───────────┘
                                                       │
                                                       ↓
                                              ┌──────────────────┐
                                              │   Neo4jProperty  │
                                              │     GraphStore   │
                                              └──────────────────┘
                                                       │
┌──────────┐    ┌────────────────┐    ┌───────────┐     │
│  CLI     │→───│ FastAPI /run   │→───│  Neo4j    │     │
│ (load,   │    │(LLM→Cypher→DB) │    │  Bolt     │     │
│  watch,  │    └────────────────┘    └───────────┘     ↓
│  api)    │                                       ┌───────────┐
└──────────┘                                       │ /labels   │
                                                    │ /events   │
                                                    │ /graph    │ ←── PyVis UI  
                                                    └───────────┘
```

* **Ingestion**: `ingest.py` builds a directed graph of “PRECEDENT → DEPENDENT” edges
* **Graph store**: every cell is a `:entity` node; edges are `:DEPENDS_ON`
* **LLM layer**: llama-index Pydantic program + `ChatPromptTemplate` → Cypher
* **Watcher**: `sync_watch.py` monitors file, re-upserts graph, POSTs `/notify_update`
* **UI**: single-page at `/graph`, dynamic highlighting via vis-network + SSE

---
