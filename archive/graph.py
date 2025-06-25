#!/usr/bin/env python3
import sys
import json
import networkx as nx
from pyvis.network import Network

def main(json_file: str):
    data = json.load(open(json_file))
    src = data["source"]
    deps = data["dependents"]

    G = nx.DiGraph()
    for d in deps:
        G.add_edge(src, d)

    # create a PyVis network (non‐notebook mode)
    net = Network(directed=True, notebook=False, height="600px", width="100%")
    net.from_nx(G)
    net.write_html("dependents.html")
    print("Wrote dependents.html")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python graph.py <out.json>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
