import typer, pathlib, json
from .ingest import build_nx_graph
from .graph_store import clear_db, upsert_graph
from .sync_watch import main as watch_main
from .api import app as fastapi_app
import uvicorn

cli = typer.Typer(help="🧠 Spreadsheet-Brain CLI")


@cli.command()
def load(xlsx: str):
    """One-shot: parse spreadsheet & push to Neo4j."""
    g = build_nx_graph(xlsx)
    clear_db(); upsert_graph(g)
    typer.echo("✅  Graph loaded")


@cli.command()
def impact(cell: str):
    """Print all dependents of CELL using Cypher."""
    from .api import impact
    print(json.dumps(impact({"cell": cell}), indent=2))


@cli.command()
def watch(xlsx: str):
    """Watch XLSX and auto-sync to Neo4j."""
    watch_main(xlsx)


@cli.command()
def api(host: str = "0.0.0.0", port: int = 8000):
    """Launch REST API."""
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
