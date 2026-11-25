"""Kommandoradsverktyg för att bygga databasen, hämta källor, exportera react-force-graph & starta MCP."""

from __future__ import annotations

import argparse
import json

from .db import DEFAULT_DB_PATH, ROOT_DIR, get_connection, init_db
from .exporters import export_all_formats
from .ingest_riksdagen import ingest_core_sfs_from_riksdagen
from .mcp_server import run_server
from .scope_guard import ScopeGuard
from .seed import seed_knowledge_graph


def cmd_build(skip_riksdagen: bool = False) -> None:
    sources_yaml = ROOT_DIR / "config" / "sources.yaml"
    guard = ScopeGuard.from_sources_yaml(sources_yaml)

    with get_connection(DEFAULT_DB_PATH) as conn:
        init_db(conn, reset_graph=True)
        graph_stats = seed_knowledge_graph(conn, sources_yaml)
        doc_stats = {"documents": 0, "chunks": 0, "skipped": 0}
        if not skip_riksdagen:
            doc_stats = ingest_core_sfs_from_riksdagen(conn, guard)
        exported = export_all_formats(conn, ROOT_DIR)

    print(
        json.dumps(
            {
                "status": "ok",
                "database": str(DEFAULT_DB_PATH),
                "knowledge_graph": graph_stats,
                "riksdagen_sfs": doc_stats,
                "exports": {k: str(v.relative_to(ROOT_DIR)) for k, v in exported.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Svenskt Totalförsvar – Kunskapsgraf, RAG & MCP")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Bygger SQLite-kunskapsgraf, hämtar SFS och exporterar alla format inkl. react-force-graph.")
    p_build.add_argument("--skip-riksdagen", action="store_true", help="Bygg endast graf och exporter utan API-anrop.")

    sub.add_parser("serve", help="Startar MCP-servern över stdio.")

    args = parser.parse_args()
    if args.command == "build":
        cmd_build(skip_riksdagen=args.skip_riksdagen)
    elif args.command == "serve":
        run_server()


if __name__ == "__main__":
    main()
