"""Exportmotor för react-force-graph (JSON), Markdown/Mermaid (L1–L2) och CSV/JSON."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .db import ROOT_DIR


NODE_VISUAL_CONFIG: dict[str, dict[str, Any]] = {
    "pillar": {"color": "#fbbf24", "val": 28, "label_sv": "Huvudpelare"},
    "governance": {"color": "#f59e0b", "val": 18, "label_sv": "Riksdag, Regering & Styrning"},
    "nato_framework": {"color": "#38bdf8", "val": 24, "label_sv": "NATO & Alliansen"},
    "nato_mechanism": {"color": "#0ea5e9", "val": 15, "label_sv": "NATO-system (NCRS / HNS / NDPP)"},
    "nato_requirement": {"color": "#0284c7", "val": 14, "label_sv": "NATO:s 7 Grundkrav (Artikel 3)"},
    "sector": {"color": "#10b981", "val": 18, "label_sv": "Beredskapssektor (12 st)"},
    "agency": {"color": "#34d399", "val": 9, "label_sv": "Statlig myndighet"},
    "civilomrade": {"color": "#a855f7", "val": 16, "label_sv": "Civilområde (6 st)"},
    "county": {"color": "#c084fc", "val": 7, "label_sv": "Länsstyrelse / Län (21 st)"},
    "regional_umbrella": {"color": "#e879f9", "val": 14, "label_sv": "Kommuner & Regioner (SKR)"},
    "law": {"color": "#f43f5e", "val": 12, "label_sv": "Lag & Förordning (SFS)"},
    "ffo_hub": {"color": "#fb923c", "val": 15, "label_sv": "Frivilligförsvaret (Nav)"},
    "ffo": {"color": "#fdba74", "val": 6, "label_sv": "Frivillig försvarsorganisation (18 FFO)"},
    "academia_hub": {"color": "#22d3ee", "val": 16, "label_sv": "Campus totalförsvar (Nav)"},
    "university": {"color": "#67e8f9", "val": 5, "label_sv": "Samverkande lärosäte (37 st)"},
    "business_org": {"color": "#94a3b8", "val": 9, "label_sv": "Näringsliv & Försörjning"},
}


PERSPECTIVES: dict[str, dict[str, Any]] = {
    "helhetsbild": {
        "id": "helhetsbild",
        "title": "Helhetsbild – Hela Totalförsvaret",
        "description": "Samtliga aktörer, sektorer, civilområden, lagar, NATO-krav, frivilligorganisationer och lärosäten.",
        "node_types": list(NODE_VISUAL_CONFIG.keys()),
    },
    "beredskapssektorer": {
        "id": "beredskapssektorer",
        "title": "12 Beredskapssektorer & Myndigheter",
        "description": "Civilt försvar, de 12 beredskapssektorerna, sektorsansvariga myndigheter och samtliga beredskapsmyndigheter.",
        "node_types": ["pillar", "sector", "agency"],
    },
    "nato_resiliens": {
        "id": "nato_resiliens",
        "title": "NATO, NCRS/CRM & 7 Resilienskrav",
        "description": "Hur Sveriges totalförsvar och de 12 beredskapssektorerna kopplas till NATO:s 7 grundkrav (Artikel 3), NCRS/NRS och Värdlandsstöd (HNS).",
        "node_types": ["pillar", "governance", "nato_framework", "nato_mechanism", "nato_requirement", "sector"],
    },
    "geografi_civilomraden": {
        "id": "geografi_civilomraden",
        "title": "Geografi: 6 Civilområden, 21 Län & Kommuner",
        "description": "Regional och lokal beredskapsstruktur med civilområdesansvariga länsstyrelser, alla 21 län samt SKR (290 kommuner & 21 regioner).",
        "node_types": ["pillar", "civilomrade", "county", "regional_umbrella", "law"],
    },
    "lagstiftning_styrning": {
        "id": "lagstiftning_styrning",
        "title": "Styrning, Lagrum (SFS) & Regleringsbrev",
        "description": "Riksdagen, Regeringen, regleringsbrev och hur centrala lagar och förordningar (SFS) styr totalförsvarets delar.",
        "node_types": ["pillar", "governance", "law", "sector", "civilomrade", "regional_umbrella", "nato_mechanism"],
    },
    "akademi_och_frivilliga": {
        "id": "akademi_och_frivilliga",
        "title": "Campus Totalförsvar (37 lärosäten), 18 FFO & Näringsliv",
        "description": "Utbildning och forskning via Campus totalförsvar, folkrörelseförankring via de 18 frivilliga försvarsorganisationerna samt näringslivets roll.",
        "node_types": ["pillar", "academia_hub", "university", "ffo_hub", "ffo", "business_org"],
    },
}


def build_force_graph_payload(
    conn: sqlite3.Connection,
    perspective: str = "helhetsbild",
    center_node_id: str | None = None,
    max_hops: int = 2,
) -> dict[str, Any]:
    """Bygger ett { metadata, perspectives, nodeTypes, nodes, links }-objekt för react-force-graph."""
    persp = PERSPECTIVES.get(perspective, PERSPECTIVES["helhetsbild"])
    allowed_types = set(persp["node_types"])

    rows_nodes = conn.execute("SELECT * FROM nodes ORDER BY type, name").fetchall()
    rows_edges = conn.execute("SELECT * FROM edges ORDER BY weight DESC, id ASC").fetchall()

    in_deg_map: dict[str, int] = {}
    out_deg_map: dict[str, int] = {}
    weight_sum_map: dict[str, float] = {}
    for e in rows_edges:
        out_deg_map[e["source"]] = out_deg_map.get(e["source"], 0) + 1
        in_deg_map[e["target"]] = in_deg_map.get(e["target"], 0) + 1
        w = float(e["weight"] or 1.0)
        weight_sum_map[e["source"]] = weight_sum_map.get(e["source"], 0.0) + w
        weight_sum_map[e["target"]] = weight_sum_map.get(e["target"], 0.0) + w

    filtered_node_ids = {
        r["id"] for r in rows_nodes if r["type"] in allowed_types
    }

    if center_node_id and any(r["id"] == center_node_id for r in rows_nodes):
        # Ego-graf runt en vald nod (max_hops steg utåt/inåt)
        ego_ids = {center_node_id}
        frontier = {center_node_id}
        for _ in range(max(1, max_hops)):
            next_frontier: set[str] = set()
            for e in rows_edges:
                if e["source"] in frontier and e["target"] not in ego_ids:
                    next_frontier.add(e["target"])
                if e["target"] in frontier and e["source"] not in ego_ids:
                    next_frontier.add(e["source"])
            ego_ids |= next_frontier
            frontier = next_frontier
        filtered_node_ids = ego_ids

    nodes_out: list[dict[str, Any]] = []
    for r in rows_nodes:
        if r["id"] not in filtered_node_ids:
            continue
        vis = NODE_VISUAL_CONFIG.get(r["type"], {"color": "#cbd5e1", "val": 8, "label_sv": r["type"]})
        meta = json.loads(r["metadata_json"] or "{}")
        aliases = json.loads(r["aliases_json"] or "[]")
        in_deg = in_deg_map.get(r["id"], 0)
        out_deg = out_deg_map.get(r["id"], 0)
        deg = in_deg + out_deg
        w_sum = round(weight_sum_map.get(r["id"], 1.0), 2)

        # Berika beskrivning för myndigheter som ingår i en eller flera beredskapssektorer
        desc = r["description"]
        if r["type"] == "agency":
            lead_secs = [
                row["short_name"]
                for row in conn.execute(
                    "SELECT n.short_name FROM edges e JOIN nodes n ON n.id = e.target WHERE e.source = ? AND e.relation = 'SEKTORSANSVARIG_FOR'",
                    (r["id"],),
                ).fetchall()
            ]
            mem_secs = [
                row["short_name"]
                for row in conn.execute(
                    "SELECT n.short_name FROM edges e JOIN nodes n ON n.id = e.target WHERE e.source = ? AND e.relation = 'INGAR_I_SEKTOR'",
                    (r["id"],),
                ).fetchall()
            ]
            parts: list[str] = []
            if lead_secs:
                parts.append(f"Sektorsansvarig myndighet för: {', '.join(lead_secs)}.")
            if mem_secs:
                parts.append(f"Ingår som beredskapsmyndighet i: {', '.join(mem_secs)}.")
            if parts:
                desc = " ".join(parts) + (f" ({r['domain']})" if r["domain"] else "")

        # Volym/area-viktning baserad på in- och utgående kopplingar samt relationsvikt
        radius_score = 2.0 + (w_sum ** 0.65) * 1.45
        weighted_val = round(radius_score ** 2.4, 1)

        nodes_out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "shortName": r["short_name"] or r["name"],
                "type": r["type"],
                "typeLabel": vis["label_sv"],
                "color": vis["color"],
                "val": weighted_val,
                "degree": deg,
                "inDegree": in_deg,
                "outDegree": out_deg,
                "weightedDegree": w_sum,
                "domain": r["domain"],
                "url": r["url"],
                "description": desc,
                "aliases": aliases,
                "metadata": meta,
            }
        )

    links_out: list[dict[str, Any]] = []
    for e in rows_edges:
        if e["source"] in filtered_node_ids and e["target"] in filtered_node_ids:
            links_out.append(
                {
                    "source": e["source"],
                    "target": e["target"],
                    "relation": e["relation"],
                    "weight": e["weight"],
                }
            )

    return {
        "metadata": {
            "project": "Svenskt Totalförsvar – Kunskapsgraf & MCP",
            "repo": "https://github.com/flinnander/totalforsvaret",
            "activePerspective": persp["id"],
            "nodeCount": len(nodes_out),
            "linkCount": len(links_out),
            "scopePolicy": "Endast öppna normativa och organisatoriska källor (SECURITY_AND_SCOPE.md).",
        },
        "perspectives": list(PERSPECTIVES.values()),
        "nodeTypes": NODE_VISUAL_CONFIG,
        "nodes": nodes_out,
        "links": links_out,
    }


def export_all_formats(conn: sqlite3.Connection, root_dir: Path = ROOT_DIR) -> dict[str, Path]:
    """Genererar alla statiska utdatafiler (react-force-graph JSON, Markdown/Mermaid, CSV och JSON)."""
    graph_dir = root_dir / "exports" / "graph"
    md_dir = root_dir / "exports" / "markdown"
    json_dir = root_dir / "exports" / "json"
    csv_dir = root_dir / "exports" / "csv"
    web_data_dir = root_dir / "web" / "public" / "data"

    for d in (graph_dir, md_dir, json_dir, csv_dir, web_data_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. react-force-graph master JSON (används både av webbappen och som export)
    full_graph = build_force_graph_payload(conn, perspective="helhetsbild")
    fg_path = graph_dir / "force_graph.json"
    fg_text = json.dumps(full_graph, ensure_ascii=False, indent=2)
    fg_path.write_text(fg_text, encoding="utf-8")
    (web_data_dir / "force_graph.json").write_text(fg_text, encoding="utf-8")

    # 2. Aktörslista i JSON & CSV
    actors_json_path = json_dir / "actors.json"
    actors_json_path.write_text(
        json.dumps(full_graph["nodes"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    actors_csv_path = csv_dir / "actors.csv"
    with actors_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "type_label", "name", "short_name", "domain", "url", "description"])
        for n in full_graph["nodes"]:
            writer.writerow(
                [n["id"], n["type"], n["typeLabel"], n["name"], n["shortName"], n["domain"] or "", n["url"] or "", n["description"]]
            )

    # 3. Markdown L1: Exekutiv översikt med Mermaid-karta
    sectors = conn.execute("SELECT * FROM nodes WHERE type = 'sector' ORDER BY name").fetchall()
    civilomraden = conn.execute("SELECT * FROM nodes WHERE type = 'civilomrade' ORDER BY name").fetchall()
    nato_reqs = conn.execute("SELECT * FROM nodes WHERE type = 'nato_requirement' ORDER BY id").fetchall()
    laws = conn.execute("SELECT * FROM nodes WHERE type = 'law' ORDER BY short_name").fetchall()
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]

    l1_md = f"""# Svenskt Totalförsvar – Exekutiv Helhetsbild (Nivå L1)

> Automatgenererad ur projektets kunskapsgraf (`{len(full_graph['nodes'])}` noder, `{len(full_graph['links'])}` kopplingar, `{doc_count}` indexerade rättskällor med `{chunk_count}` sökbara textavsnitt).

## Systemkarta

```mermaid
flowchart TD
    Riksdagen["Sveriges riksdag (Lagar & Budget)"] --> TF["Sveriges Totalförsvar"]
    Regeringen["Regeringen (Förordningar & Regleringsbrev)"] --> TF
    TF <--> NATO["NATO & Alliansramverk (Artikel 3, NCRS/CRM, HNS, NDPP)"]
    TF --> MF["Militärt försvar (Försvarsmakten, Militärregioner & Stödmyndigheter)"]
    TF --> CF["Civilt försvar (Samhällets samlade motståndskraft)"]
    CF --> Sektorer["12 Beredskapssektorer (~67 Beredskapsmyndigheter)"]
    CF --> Civilomr["6 Civilområden (21 Länsstyrelser)"]
    CF --> KommunRegion["290 Kommuner & 21 Regioner (LEH / SKR)"]
    TF --> FFO["18 Frivilliga försvarsorganisationer (FFO)"]
    TF --> Campus["Campus totalförsvar (37 Svenska lärosäten)"]
    CF --> Naringsliv["Näringsliv & Försörjningsberedskap"]
```

## Nyckeltal i strukturen
* **12 nationella beredskapssektorer** med var sin sektorsansvarig myndighet enligt *förordning (2022:524)*.
* **6 geografiska civilområden** ledda av civilområdesansvariga länsstyrelser i samspel med 21 län/regioner och 290 kommuner.
* **7 grundläggande NATO-krav på civil motståndskraft** (*Seven Baseline Requirements*, Artikel 3) mappade direkt mot Sveriges beredskapssektorer.
* **18 frivilliga försvarsorganisationer (FFO)** som förstärker både militärt och civilt försvar.
* **37 universitet och högskolor** förenade i **Campus totalförsvar** för forskning och utbildning.

## Centrala lagar och förordningar (SFS)
"""
    for law in laws:
        l1_md += f"- **{law['short_name']}** – [{law['name']}]({law['url']}): {law['description']}\n"

    l1_path = md_dir / "OVERSIKT_L1.md"
    l1_path.write_text(l1_md, encoding="utf-8")

    # 4. Markdown L2: De 12 Beredskapssektorerna & NATO-mappning
    l2_sec_md = "# De 12 Beredskapssektorerna & NATO-mappning (Nivå L2)\n\n"
    for sec in sectors:
        lead_row = conn.execute(
            """
            SELECT n.* FROM edges e
            JOIN nodes n ON n.id = e.source
            WHERE e.target = ? AND e.relation = 'SEKTORSANSVARIG_FOR'
            """,
            (sec["id"],),
        ).fetchone()
        member_rows = conn.execute(
            """
            SELECT n.* FROM edges e
            JOIN nodes n ON n.id = e.source
            WHERE e.target = ? AND e.relation = 'INGAR_I_SEKTOR'
            ORDER BY n.name
            """,
            (sec["id"],),
        ).fetchall()
        nato_rows = conn.execute(
            """
            SELECT n.* FROM edges e
            JOIN nodes n ON n.id = e.target
            WHERE e.source = ? AND e.relation = 'MAPPAR_MOT_NATO_KRAV'
            ORDER BY n.id
            """,
            (sec["id"],),
        ).fetchall()

        l2_sec_md += f"## {sec['short_name']}\n"
        if lead_row:
            l2_sec_md += f"- **Sektorsansvarig myndighet:** [{lead_row['name']}]({lead_row['url']})\n"
        if member_rows:
            members_str = ", ".join(f"[{m['short_name']}]({m['url']})" for m in member_rows)
            l2_sec_md += f"- **Ingående beredskapsmyndigheter:** {members_str}\n"
        if nato_rows:
            nato_str = ", ".join(f"*{nr['short_name']}*" for nr in nato_rows)
            l2_sec_md += f"- **Mappar mot NATO Artikel 3-grundkrav:** {nato_str}\n"
        l2_sec_md += "\n"

    l2_sec_path = md_dir / "BEREDSKAPSSEKTORER_L2.md"
    l2_sec_path.write_text(l2_sec_md, encoding="utf-8")

    # 5. Markdown L2: NATO, NCRS/CRM & 7 Baseline Requirements
    l2_nato_md = """# NATO, NCRS/CRM & De 7 Grundkraven i Svenskt Totalförsvar (Nivå L2)

> **Avgränsning:** Beskriver uteslutande öppna konceptuella och förvaltningsrättsliga ramverk enligt `SECURITY_AND_SCOPE.md`.

## Ramverksmekanismer
"""
    mechs = conn.execute("SELECT * FROM nodes WHERE type = 'nato_mechanism' ORDER BY id").fetchall()
    for m in mechs:
        l2_nato_md += f"### {m['name']}\n{m['description']}\n\n"

    l2_nato_md += "## NATO:s sju grundläggande krav på civil motståndskraft (Artikel 3)\n\n"
    for nr in nato_reqs:
        mapped_secs = conn.execute(
            """
            SELECT n.short_name FROM edges e
            JOIN nodes n ON n.id = e.source
            WHERE e.target = ? AND e.relation = 'MAPPAR_MOT_NATO_KRAV'
            ORDER BY n.short_name
            """,
            (nr["id"],),
        ).fetchall()
        sec_names = ", ".join(s["short_name"] for s in mapped_secs) or "Tvärsektoriellt"
        l2_nato_md += f"### {nr['short_name']}\n- **Beskrivning:** {nr['description']}\n- **Primära svenska beredskapssektorer:** {sec_names}\n\n"

    l2_nato_path = md_dir / "NATO_OCH_NCRS_L2.md"
    l2_nato_path.write_text(l2_nato_md, encoding="utf-8")

    # 6. Markdown L2: De 6 Civilområdena
    l2_civ_md = "# Sveriges 6 Civilområden & Regional Ledning (Nivå L2)\n\n"
    for civ in civilomraden:
        meta = json.loads(civ["metadata_json"] or "{}")
        counties_str = ", ".join(meta.get("counties", []))
        l2_civ_md += (
            f"## {civ['name']}\n"
            f"- **Civilområdesansvarig länsstyrelse:** {meta.get('lead_county_board', '')}\n"
            f"- **Ingående län:** {counties_str}\n"
            f"- **Webbplats:** [{civ['domain']}]({civ['url']})\n\n"
        )
    l2_civ_path = md_dir / "CIVILOMRADEN_L2.md"
    l2_civ_path.write_text(l2_civ_md, encoding="utf-8")

    return {
        "force_graph": fg_path,
        "actors_json": actors_json_path,
        "actors_csv": actors_csv_path,
        "oversikt_l1": l1_path,
        "beredskapssektorer_l2": l2_sec_path,
        "nato_l2": l2_nato_path,
        "civilomraden_l2": l2_civ_path,
    }
