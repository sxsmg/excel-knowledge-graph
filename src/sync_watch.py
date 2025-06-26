import time, pathlib, argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .ingest import build_nx_graph
from .graph_store import clear_db, upsert_graph
import requests

class _Handler(FileSystemEventHandler):
    def __init__(self, path):
        self.path = pathlib.Path(path).resolve()

    def on_modified(self, event):
        if pathlib.Path(event.src_path).resolve() == self.path:
            print(f"🔄  {self.path.name} changed – reloading…")
            gx = build_nx_graph(str(self.path))
            clear_db()
            upsert_graph(gx)
            requests.post("http://localhost:8000/notify_update")
            print("✅  Graph reloaded")


def main(xlsx_path: str):
    p = pathlib.Path(xlsx_path).resolve()
    gx = build_nx_graph(str(p))
    clear_db()
    upsert_graph(gx)
    obs = Observer()
    obs.schedule(_Handler(p), p.parent, recursive=False)
    obs.start()
    print(f"👀  Watching `{p}` for edits (Ctrl-C to exit)")
    try:
        while True:
            time.sleep(1)
    finally:
        obs.stop()
        obs.join()
