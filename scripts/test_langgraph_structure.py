"""STEP 1.5 smoke test: verify that LangGraph owns the workflow."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.agents.ai_ops_graph import ai_ops_graph


def main() -> None:
    graph = ai_ops_graph.get_graph()

    print("LangGraph AI Ops Investigator")
    print("=" * 72)
    print("Nodes:")
    for node_name in graph.nodes:
        print(f"  - {node_name}")

    print("\nEdges:")
    for edge in graph.edges:
        conditional = " [conditional]" if getattr(edge, "conditional", False) else ""
        print(f"  - {edge.source} -> {edge.target}{conditional}")

    print("\nMermaid:")
    print("-" * 72)
    print(graph.draw_mermaid())

    print("\nSTEP 1.5 LangGraph structure smoke test complete.")


if __name__ == "__main__":
    main()
