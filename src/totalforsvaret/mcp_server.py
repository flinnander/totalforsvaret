"""MCP-server (Model Context Protocol) för Svenskt Totalförsvar (Zoom-nivåer L1–L4 + react-force-graph)."""

from __future__ import annotations

import json
import re

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # Fallback för mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]

from .db import DEFAULT_DB_PATH, ROOT_DIR, get_connection
from .exporters import PERSPECTIVES, build_force_graph_payload


mcp = MCPServer(
    "Svenskt Totalförsvar MCP",
    instructions=(
        "Ger strukturerad och källhänvisad kunskap om det svenska totalförsvaret, "
        "beredskapssektorer, myndigheter, civilområden, lagar (SFS), Campus totalförsvar, "
        "frivilligorganisationer och NATO-ramverk (Artikel 3, NCRS/NRS, Värdlandsstöd) "
        "från övergripande L1-nivå ner till L4-paragrafnivå samt react-force-graph-data."
    ),
)


@mcp.tool()
def get_overview(format: str = "markdown") -> str:
    """Returnerar en L1-helhetsbild av det svenska totalförsvaret.

    Args:
        format: 'markdown' (med Mermaid-karta) eller 'json' (nyckeltal och huvudpelare).
    """
    md_file = ROOT_DIR / "exports" / "markdown" / "OVERSIKT_L1.md"
    if format.lower() == "markdown" and md_file.exists():
        return md_file.read_text(encoding="utf-8")

    with get_connection(DEFAULT_DB_PATH) as conn:
        counts = {
            r["type"]: r["cnt"]
            for r in conn.execute("SELECT type, COUNT(*) AS cnt FROM nodes GROUP BY type").fetchall()
        }
        return json.dumps(
            {
                "level": "L1",
                "summary": "Sveriges totalförsvar består av militärt försvar och civilt försvar i samspel med NATO.",
                "countsByNodeType": counts,
                "availablePerspectives": list(PERSPECTIVES.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )


@mcp.tool()
def explore_actor_or_sector(query: str) -> str:
    """Slår upp en myndighet, beredskapssektor, civilområde, lärosäte, FFO eller lag i kunskapsgrafen (L2–L3).

    Hanterar även historiska alias som 'MSB' -> 'Myndigheten för civilt försvar (MCF)'.
    """
    q = query.strip().lower()
    with get_connection(DEFAULT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT * FROM nodes
            WHERE lower(id) = ?
               OR lower(name) LIKE ?
               OR lower(COALESCE(short_name, '')) LIKE ?
               OR lower(aliases_json) LIKE ?
            ORDER BY CASE WHEN lower(short_name) = ? THEN 0 ELSE 1 END, length(name) ASC
            LIMIT 5
            """,
            (q, f"%{q}%", f"%{q}%", f"%{q}%", q),
        ).fetchall()

        if not rows:
            return f"Ingen aktör, sektor eller nod hittades för '{query}'."

        node = rows[0]
        outgoing = conn.execute(
            """
            SELECT e.relation, n.id, n.name, n.type, n.url
            FROM edges e JOIN nodes n ON n.id = e.target
            WHERE e.source = ?
            ORDER BY e.weight DESC
            """,
            (node["id"],),
        ).fetchall()
        incoming = conn.execute(
            """
            SELECT e.relation, n.id, n.name, n.type, n.url
            FROM edges e JOIN nodes n ON n.id = e.source
            WHERE e.target = ?
            ORDER BY e.weight DESC
            """,
            (node["id"],),
        ).fetchall()

        result = {
            "id": node["id"],
            "name": node["name"],
            "shortName": node["short_name"],
            "type": node["type"],
            "url": node["url"],
            "description": node["description"],
            "aliases": json.loads(node["aliases_json"] or "[]"),
            "metadata": json.loads(node["metadata_json"] or "{}"),
            "outgoingRelations": [dict(r) for r in outgoing],
            "incomingRelations": [dict(r) for r in incoming],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_nato_mapping(topic: str = "all") -> str:
    """Visar hur NATO:s 7 grundkrav (Artikel 3), NCRS/CRM och Värdlandsstöd (HNS) kopplas till svenskt totalförsvar (L2–L3)."""
    nato_md = ROOT_DIR / "exports" / "markdown" / "NATO_OCH_NCRS_L2.md"
    if topic.lower() in {"all", "markdown", "helhet"} and nato_md.exists():
        return nato_md.read_text(encoding="utf-8")

    return explore_actor_or_sector(topic)


@mcp.tool()
def get_force_graph_data(
    perspective: str = "helhetsbild",
    center_node_id: str | None = None,
    max_hops: int = 2,
) -> str:
    """Returnerar färdigformaterad { nodes, links }-JSON för react-force-graph ur valt perspektiv eller runt en specifik nod.

    Args:
        perspective: 'helhetsbild', 'beredskapssektorer', 'nato_resiliens', 'geografi_civilomraden',
                     'lagstiftning_styrning' eller 'akademi_och_frivilliga'.
        center_node_id: Valfritt nod-ID (t.ex. 'sector_energiforsorjning' eller 'agency_mcf') för att filtrera fram dess ego-graf.
        max_hops: Antal relationssteg ut från center_node_id (standard 2).
    """
    with get_connection(DEFAULT_DB_PATH) as conn:
        payload = build_force_graph_payload(
            conn,
            perspective=perspective,
            center_node_id=center_node_id,
            max_hops=max_hops,
        )
        return json.dumps(payload, ensure_ascii=False)


@mcp.tool()
def search_totalforsvar_sources(query: str, doc_type: str | None = None, limit: int = 6) -> str:
    """Söker på paragraf- och källtextnivå (Nivå L4) i inlästa lagar (SFS) och dokument via SQLite FTS5 BM25."""
    tokens = [re.sub(r"[^\w:§-]", "", t) for t in query.split()]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return "Ange minst ett sökord."

    fts_query = " OR ".join(f'"{t}"*' for t in tokens)

    with get_connection(DEFAULT_DB_PATH) as conn:
        sql = """
            SELECT
                f.chunk_id,
                f.doc_id,
                f.doc_type,
                f.title,
                f.section_heading,
                snippet(chunks_fts, 5, '**', '**', ' … ', 48) AS match_snippet,
                d.source_url,
                d.year,
                bm25(chunks_fts) AS score
            FROM chunks_fts f
            JOIN documents d ON d.doc_id = f.doc_id
            WHERE chunks_fts MATCH ?
        """
        params: list[object] = [fts_query]
        if doc_type:
            sql += " AND f.doc_type = ?"
            params.append(doc_type)
        sql += " ORDER BY score ASC LIMIT ?"
        params.append(max(1, min(limit, 20)))

        rows = conn.execute(sql, params).fetchall()
        hits = [dict(r) for r in rows]
        return json.dumps({"level": "L4", "query": query, "hits": hits}, ensure_ascii=False, indent=2)


def run_server() -> None:
    mcp.run()


if __name__ == "__main__":
    run_server()
