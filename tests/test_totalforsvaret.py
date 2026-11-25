"""Enhetstester för avgränsningsfilter (SECURITY_AND_SCOPE), kunskapsgraf och react-force-graph-export."""

from pathlib import Path
import json

from totalforsvaret.db import ROOT_DIR, get_connection, init_db
from totalforsvaret.exporters import build_force_graph_payload
from totalforsvaret.scope_guard import ScopeGuard
from totalforsvaret.seed import seed_knowledge_graph


def test_scope_guard_blocks_compliance_and_rsa() -> None:
    guard = ScopeGuard.from_sources_yaml(ROOT_DIR / "config" / "sources.yaml")

    ok, _ = guard.is_allowed(
        title="Förordning (2022:524) om statliga myndigheters beredskap",
        url="https://www.riksdagen.se/sv/dokument-och-lagar/",
    )
    assert ok is True

    blocked_rsa, reason = guard.is_allowed(
        title="Kommunens risk- och sårbarhetsanalys 2026",
        url="https://exempel.se/rsa-2026.pdf",
    )
    assert blocked_rsa is False
    assert reason is not None

    blocked_cap, _ = guard.is_allowed(
        title="Återrapportering och förmågebedömning av beredskap",
        url="https://exempel.se/rapport.pdf",
    )
    assert blocked_cap is False


def test_seed_and_force_graph_perspectives(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    with get_connection(db_file) as conn:
        init_db(conn, reset_graph=True)
        stats = seed_knowledge_graph(conn)
        assert stats["nodes"] >= 140
        assert stats["edges"] >= 200

        # Kontrollera Campus totalförsvar & 37 lärosäten (36 separata + FHS kopplad = 37)
        campus_links = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE target = 'academia_campus_totalforsvar' AND relation = 'SAMVERKAR_I_CAMPUS'"
        ).fetchone()[0]
        assert campus_links == 37

        # Kontrollera react-force-graph perspektiv
        nato_graph = build_force_graph_payload(conn, perspective="nato_resiliens")
        assert len(nato_graph["nodes"]) > 15
        assert len(nato_graph["links"]) > 15
        serialized = json.dumps(nato_graph, ensure_ascii=False)
        assert "nato_ncrs" in serialized
        assert "sector_energiforsorjning" in serialized


def test_mcp_tools_integration() -> None:
    from totalforsvaret.mcp_server import explore_actor_or_sector, get_force_graph_data, search_totalforsvar_sources

    msb_res = json.loads(explore_actor_or_sector("MSB"))
    assert msb_res["id"] == "agency_mcf"

    fg_res = json.loads(get_force_graph_data(perspective="geografi_civilomraden"))
    assert fg_res["metadata"]["activePerspective"] == "geografi_civilomraden"
    assert len(fg_res["nodes"]) >= 25

    sfs_res = json.loads(search_totalforsvar_sources("beredskapsmyndighet"))
    assert sfs_res["level"] == "L4"
    assert len(sfs_res["hits"]) >= 1

