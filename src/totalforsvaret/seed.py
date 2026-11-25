"""Bygger upp kunskapsgrafen i SQLite utifrån config/sources.yaml och domänstruktur."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
import yaml

from .db import ROOT_DIR, upsert_edge, upsert_node


NATO_BASELINE_REQUIREMENTS: dict[str, dict[str, str]] = {
    "continuity_of_government": {
        "name": "NATO Krav 1: Politiskt beslutsfattande & centrala ledningsfunktioner",
        "short_name": "1. Beslutsfattande & Ledning",
        "description": "Säkerställa kontinuitet i statsledning, regering, riksdag och kritiska offentliga tjänster under alla förhållanden (Artikel 3).",
    },
    "resilient_energy_supplies": {
        "name": "NATO Krav 2: Resilient energiförsörjning",
        "short_name": "2. Energiförsörjning",
        "description": "Trygga tillförlitlig elförsörjning, bränsleförsörjning och energidistribution även vid angrepp eller störningar.",
    },
    "uncontrolled_movement_of_people": {
        "name": "NATO Krav 3: Hantera okontrollerade befolkningsrörelser",
        "short_name": "3. Befolkningsrörelser & Utrymning",
        "description": "Förmåga att hantera omfattande utrymningar, evakuering och plötsliga befolkningsrörelser utan att hindra militära rörelser.",
    },
    "resilient_food_and_water_resources": {
        "name": "NATO Krav 4: Resilient livsmedels- och dricksvattenförsörjning",
        "short_name": "4. Livsmedel & Dricksvatten",
        "description": "Säkerställa tillgång till mat och rent dricksvatten för civilbefolkning och militära styrkor under kris och krig.",
    },
    "ability_to_deal_with_mass_casualties": {
        "name": "NATO Krav 5: Hantera masskadeutfall & hälsokriser",
        "short_name": "5. Masskadeutfall & Sjukvård",
        "description": "Sjukvårdens, läkemedelsförsörjningens och räddningstjänstens förmåga att hantera stora mängder skadade och akuta hälsokriser.",
    },
    "resilient_civil_communications": {
        "name": "NATO Krav 6: Resilienta civila kommunikationssystem",
        "short_name": "6. Civila kommunikationer & Cyber",
        "description": "Robusta och säkra telekom-, fiber-, post- och digitala kommunikationsnät.",
    },
    "resilient_transport_systems": {
        "name": "NATO Krav 7: Resilienta transportsystem",
        "short_name": "7. Transportsystem",
        "description": "Säkerställa att vägar, järnvägar, hamnar och flygplatser kan bära både samhällsviktiga transporter och allierade styrkors rörelser.",
    },
}


CORE_SFS_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "1992:1403": (
        "Lag (1992:1403) om totalförsvar och höjd beredskap",
        "Grundläggande lag som definierar totalförsvaret (militärt och civilt försvar) samt beredskapsgraderna skärpt beredskap och högsta beredskap.",
    ),
    "2015:1053": (
        "Förordning (2015:1053) om totalförsvar och höjd beredskap",
        "Reglerar krigsorganisation, beredskapslarm och myndigheters planering för höjd beredskap.",
    ),
    "2022:524": (
        "Förordning (2022:524) om statliga myndigheters beredskap",
        "Beredskapsförordningen som pekar ut Sveriges ~67 beredskapsmyndigheter, de 12 beredskapssektorerna, sektorsansvariga myndigheter och de 6 civilområdena.",
    ),
    "2006:544": (
        "Lag (2006:544) om kommuners och regioners åtgärder inför och vid extraordinära händelser i fredstid och höjd beredskap (LEH)",
        "Styr kommunernas (290 st) och regionernas (21 st) ansvar under kris och höjd beredskap.",
    ),
    "2006:637": (
        "Förordning (2006:637) om kommuners och regioners åtgärder inför och vid extraordinära händelser i fredstid och höjd beredskap",
        "Kompletterande förordning till LEH avseende geografiskt områdesansvar och planering.",
    ),
    "1994:1809": (
        "Lag (1994:1809) om totalförsvarsplikt",
        "Reglerar värnplikt, civilplikt och allmän tjänsteplikt för alla som bor i Sverige mellan 16 och 70 års ålder.",
    ),
    "1982:1004": (
        "Lag (1982:1004) om skyldighet för näringsidkare, arbetsmarknadsorganisationer m.fl. att delta i totalförsvarsplaneringen",
        "Grunden för näringslivets medverkan i totalförsvarsplaneringen och utpekande av samhällsviktiga företag (K-företag).",
    ),
    "1978:599": (
        "Förfogandelag (1978:599)",
        "Ger staten rätt att under krig eller höjd beredskap ta i anspråk egendom och tjänster som behövs för totalförsvaret.",
    ),
    "1978:561": (
        "Ransoneringslag (1978:561)",
        "Möjliggör reglering och ransonering av livsmedel, drivmedel och andra förnödenheter vid försörjningskriser eller krig.",
    ),
    "2018:585": (
        "Säkerhetsskyddslag (2018:585)",
        "Normativt regelverk för skydd av säkerhetskänslig verksamhet och säkerhetsskyddsklassificerade uppgifter.",
    ),
    "2020:782": (
        "Lag (2020:782) om operativt militärt stöd",
        "Reglerar ramarna för mottagande och lämnande av militärt stöd samt värdlandsstöd i samverkan med allierade.",
    ),
}


def _slugify(value: str) -> str:
    s = value.lower()
    for a, b in (("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def seed_knowledge_graph(
    conn: sqlite3.Connection,
    sources_yaml_path: Path | None = None,
) -> dict[str, int]:
    yaml_path = sources_yaml_path or (ROOT_DIR / "config" / "sources.yaml")
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    # 1. Övergripande pelare (Pillars)
    upsert_node(
        conn,
        node_id="totalforsvaret",
        node_type="pillar",
        name="Sveriges Totalförsvar",
        short_name="Totalförsvaret",
        url="https://www.regeringen.se/regeringens-politik/totalforsvar/",
        description="All verksamhet som behövs för att förbereda Sverige för krig. Består av militärt försvar och civilt försvar i samverkan inom ramen för NATO-medlemskapet.",
    )
    upsert_node(
        conn,
        node_id="militart_forsvar",
        node_type="pillar",
        name="Militärt försvar",
        short_name="Militärt försvar",
        url="https://www.forsvarsmakten.se",
        description="Försvarsmakten (inkl. Hemvärnet och militärregionerna) tillsammans med stödjande försvarsmyndigheter och frivilliga försvarsorganisationer.",
    )
    upsert_node(
        conn,
        node_id="civilt_forsvar",
        node_type="pillar",
        name="Civilt försvar",
        short_name="Civilt försvar",
        url="https://www.mcf.se",
        description="Samhällets samlade motståndskraft vid krigsfara och krig: skydda civilbefolkningen, säkerställa de viktigaste samhällsfunktionerna och stödja Försvarsmakten och allierade.",
    )
    upsert_node(
        conn,
        node_id="nato_alliansen",
        node_type="nato_framework",
        name="NATO & Alliansramverk",
        short_name="NATO",
        domain="nato.int",
        url="https://www.nato.int",
        description="Nordatlantiska fördragsorganisationen. Sveriges totalförsvar är integrerat i NATO:s kollektiva försvar, försvarsplanering (NDPP), krishanteringssystem (NCRS/NRS) och Artikel 3-krav på civil motståndskraft.",
    )

    upsert_edge(conn, source="militart_forsvar", target="totalforsvaret", relation="DEL_AV", weight=3.0)
    upsert_edge(conn, source="civilt_forsvar", target="totalforsvaret", relation="DEL_AV", weight=3.0)
    upsert_edge(conn, source="totalforsvaret", target="nato_alliansen", relation="INTEGRERAD_MED", weight=2.5)

    # 2. Statsmakterna & Regleringsbrev
    upsert_node(
        conn,
        node_id="riksdagen",
        node_type="governance",
        name="Sveriges riksdag",
        short_name="Riksdagen",
        domain="riksdagen.se",
        url="https://www.riksdagen.se",
        description="Stiftar lagar (SFS), beslutar om statsbudgeten (Utgiftsområde 6 m.fl.) och fastställer totalförsvarsbeslut.",
    )
    upsert_node(
        conn,
        node_id="regeringen",
        node_type="governance",
        name="Regeringen & Regeringskansliet",
        short_name="Regeringen",
        domain="regeringen.se",
        url="https://www.regeringen.se",
        description="Styr riket och beslutar om höjd beredskap, förordningar och myndigheternas årliga regleringsbrev (inkl. Försvarsdepartementet och ministern för civilt försvar).",
    )
    upsert_node(
        conn,
        node_id="esv_regleringsbrev",
        node_type="governance",
        name="Statsliggaren / Regleringsbrev (ESV)",
        short_name="Regleringsbrev (ESV)",
        domain="esv.se",
        url="https://www.esv.se/statsliggaren/",
        description="Regeringens årliga styrinstrument med formella mål, totalförsvarsuppdrag och anslag till statliga myndigheter.",
    )
    upsert_node(
        conn,
        node_id="riksbanken",
        node_type="agency",
        name="Sveriges riksbank",
        short_name="Riksbanken",
        domain="riksbank.se",
        url="https://www.riksbank.se/sv/betalningar--kontanter/beredskap/",
        description="Riksdagens myndighet med övergripande ansvar för betalningssystemets och kontantförsörjningens motståndskraft under fredstida kriser och höjd beredskap.",
    )

    upsert_edge(conn, source="riksdagen", target="totalforsvaret", relation="BESLUTAR_RAMAR_FOR", weight=2.5)
    upsert_edge(conn, source="regeringen", target="totalforsvaret", relation="LEDER_OCH_STYR", weight=2.5)
    upsert_edge(conn, source="regeringen", target="esv_regleringsbrev", relation="UTFARDAR", weight=2.0)
    upsert_edge(conn, source="riksbanken", target="riksdagen", relation="MYNDIGHET_UNDER", weight=1.5)
    upsert_edge(conn, source="riksbanken", target="civilt_forsvar", relation="BIDRAR_TILL", weight=1.5)

    # 3. NATO:s 7 grundkrav + NCRS/NRS + HNS + NDPP
    nato_mechanisms = [
        (
            "nato_ncrs",
            "NATO Crisis Response System (NCRS / NRS) & Crisis Response Measures (CRM)",
            "NCRS / CRM",
            "https://www.nato.int/cps/en/natohq/topics_49288.htm",
            "NATO:s krishanteringssystem för koordinerade politiska, civila och militära åtgärder (Crisis Response Measures) som i Sverige omsätts via regeringsbeslut, beredskapsåtgärder och höjd beredskap.",
        ),
        (
            "nato_hns",
            "Värdlandsstöd (Host Nation Support, HNS) & DCA",
            "Värdlandsstöd (HNS)",
            "https://www.forsvarsmakten.se",
            "Civilt och militärt stöd som Sverige lämnar till allierade styrkor som befinner sig på, verkar i eller transiterar genom svenskt territorium.",
        ),
        (
            "nato_ndpp",
            "NATO Defence Planning Process (NDPP)",
            "NDPP",
            "https://www.nato.int",
            "NATO:s gemensamma försvarsplaneringsprocess som harmoniserar förmågemål med svensk totalförsvarsplanering.",
        ),
    ]
    for nid, nname, sname, nurl, ndesc in nato_mechanisms:
        upsert_node(
            conn,
            node_id=nid,
            node_type="nato_mechanism",
            name=nname,
            short_name=sname,
            domain="nato.int",
            url=nurl,
            description=ndesc,
        )
        upsert_edge(conn, source=nid, target="nato_alliansen", relation="DEL_AV", weight=2.0)
        upsert_edge(conn, source="totalforsvaret", target=nid, relation="OMFATTAS_AV_RAMVERK", weight=2.0)

    upsert_edge(conn, source="regeringen", target="nato_ncrs", relation="BESLUTAR_SVENSKA_ATGARDER_ENLIGT", weight=2.0)
    upsert_edge(conn, source="militart_forsvar", target="nato_hns", relation="SAMORDNAR", weight=1.8)
    upsert_edge(conn, source="civilt_forsvar", target="nato_hns", relation="LEVERERAR_STOD_TILL", weight=1.8)

    for req_key, req_info in NATO_BASELINE_REQUIREMENTS.items():
        node_id = f"nato_req_{req_key}"
        upsert_node(
            conn,
            node_id=node_id,
            node_type="nato_requirement",
            name=req_info["name"],
            short_name=req_info["short_name"],
            domain="nato.int",
            url="https://www.nato.int/cps/en/natohq/topics_132722.htm",
            description=req_info["description"],
        )
        upsert_edge(conn, source=node_id, target="nato_alliansen", relation="ARTIKEL_3_GRUNDKRAV", weight=2.0)

    # 4. Kärnlagstiftning (SFS)
    for sfs_num, (law_title, law_desc) in CORE_SFS_DESCRIPTIONS.items():
        law_id = f"sfs_{sfs_num.replace(':', '_')}"
        upsert_node(
            conn,
            node_id=law_id,
            node_type="law",
            name=law_title,
            short_name=f"SFS {sfs_num}",
            domain="riksdagen.se",
            url=f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/_sfs-{sfs_num.replace(':', '-')}/",
            description=law_desc,
            metadata={"sfs": sfs_num},
        )
        upsert_edge(conn, source="riksdagen", target=law_id, relation="UTFARDAR_FORFATTNING", weight=1.2)

    upsert_edge(conn, source="totalforsvaret", target="sfs_1992_1403", relation="STYRS_AV_LAG", weight=2.5)
    upsert_edge(conn, source="totalforsvaret", target="sfs_2015_1053", relation="STYRS_AV_LAG", weight=2.0)
    upsert_edge(conn, source="civilt_forsvar", target="sfs_2022_524", relation="STYRS_AV_LAG", weight=2.5)
    upsert_edge(conn, source="totalforsvaret", target="sfs_1994_1809", relation="STYRS_AV_LAG", weight=2.0)
    upsert_edge(conn, source="nato_hns", target="sfs_2020_782", relation="STYRS_AV_LAG", weight=1.8)

    # 5. Försvarsdepartementets myndigheter & kärnaktörer
    for agency in cfg.get("defense_and_core_agencies", []):
        aid = f"agency_{agency['id']}"
        aliases = agency.get("legacy_aliases", [])
        upsert_node(
            conn,
            node_id=aid,
            node_type="agency",
            name=agency["name"],
            short_name=agency["name"].split("(")[0].strip(),
            domain=agency["domain"],
            url=f"https://www.{agency['domain']}",
            description=agency.get("scope_notes", f"Central försvars- eller totalförsvarsmyndighet ({agency['domain']})."),
            aliases=aliases,
            metadata={"category": "defense_and_core", "doc_types": agency.get("doc_types", [])},
        )
        if agency["id"] in {"forsvarsmakten", "fmv", "fra_ncsc", "fortifikationsverket"}:
            upsert_edge(conn, source=aid, target="militart_forsvar", relation="INGAR_I", weight=2.2)
        elif agency["id"] in {"mcf", "mpf"}:
            upsert_edge(conn, source=aid, target="civilt_forsvar", relation="SAMORDNAR_OCH_STODJER", weight=2.2)
        else:
            upsert_edge(conn, source=aid, target="totalforsvaret", relation="STODJER_TOTALFORSVARET", weight=1.8)
        upsert_edge(conn, source="esv_regleringsbrev", target=aid, relation="STYR_MED_UPPDRAG", weight=1.0)

    # 6. De 12 Beredskapssektorerna & samtliga beredskapsmyndigheter
    for sec in cfg.get("preparedness_sectors", []):
        sec_id = f"sector_{sec['sector_id']}"
        upsert_node(
            conn,
            node_id=sec_id,
            node_type="sector",
            name=f"Beredskapssektor: {sec['name']}",
            short_name=sec["name"],
            url="https://www.mcf.se",
            description=f"En av Sveriges 12 nationella beredskapssektorer enligt förordning (2022:524) om statliga myndigheters beredskap.",
            metadata={"sector_key": sec["sector_id"]},
        )
        upsert_edge(conn, source=sec_id, target="civilt_forsvar", relation="DEL_AV", weight=2.2)
        upsert_edge(conn, source=sec_id, target="sfs_2022_524", relation="REGLERAS_AV", weight=1.5)

        for nato_key in sec.get("nato_baseline_mapping", []):
            upsert_edge(
                conn,
                source=sec_id,
                target=f"nato_req_{nato_key}",
                relation="MAPPAR_MOT_NATO_KRAV",
                weight=2.0,
            )

        lead = sec["lead_agency"]
        lead_id = f"agency_{lead['id']}"
        upsert_node(
            conn,
            node_id=lead_id,
            node_type="agency",
            name=lead["name"],
            short_name=lead["name"].split("(")[0].strip(),
            domain=lead["domain"],
            url=f"https://www.{lead['domain']}",
            description=f"Sektorsansvarig beredskapsmyndighet för sektorn {sec['name']}.",
            metadata={"is_preparedness_agency": True, "is_sector_lead": True},
        )
        upsert_edge(conn, source=lead_id, target=sec_id, relation="SEKTORSANSVARIG_FOR", weight=2.5)
        upsert_edge(conn, source="esv_regleringsbrev", target=lead_id, relation="STYR_MED_UPPDRAG", weight=1.0)

        for mem in sec.get("member_agencies", []):
            mem_id = f"agency_{mem['id']}"
            upsert_node(
                conn,
                node_id=mem_id,
                node_type="agency",
                name=mem["name"],
                short_name=mem["name"].split("(")[0].strip(),
                domain=mem["domain"],
                url=f"https://www.{mem['domain']}",
                description=f"Beredskapsmyndighet enligt SFS 2022:524.",
                metadata={"is_preparedness_agency": True},
            )
            upsert_edge(conn, source=mem_id, target=sec_id, relation="INGAR_I_SEKTOR", weight=1.6)
            upsert_edge(conn, source="esv_regleringsbrev", target=mem_id, relation="STYR_MED_UPPDRAG", weight=0.8)

    for sa in cfg.get("standalone_preparedness_agencies", []):
        sa_id = f"agency_{sa['id']}"
        upsert_node(
            conn,
            node_id=sa_id,
            node_type="agency",
            name=sa["name"],
            short_name=sa["name"].split("(")[0].strip(),
            domain=sa["domain"],
            url=f"https://www.{sa['domain']}",
            description="Fristående beredskapsmyndighet enligt SFS 2022:524 utanför den fasta sektorsindelningen.",
            metadata={"is_preparedness_agency": True, "standalone": True},
        )
        upsert_edge(conn, source=sa_id, target="civilt_forsvar", relation="INGAR_I", weight=1.6)
        upsert_edge(conn, source=sa_id, target="sfs_2022_524", relation="REGLERAS_AV", weight=1.2)

    # 7. De 6 Civilområdena, 21 Län/Länsstyrelser & SKR/Kommuner
    reg_cfg = cfg.get("regional_and_municipal_sources", {})
    for civ in reg_cfg.get("civilomraden", []):
        civ_id = f"civilomrade_{civ['id']}"
        upsert_node(
            conn,
            node_id=civ_id,
            node_type="civilomrade",
            name=civ["name"],
            short_name=civ["name"],
            domain=civ["domain"],
            url=f"https://www.{civ['domain']}",
            description=f"Regional samordningsnivå i det civila försvaret. Civilområdesansvarig: {civ['lead_county_board']}.",
            metadata={"lead_county_board": civ["lead_county_board"], "counties": civ["counties"]},
        )
        upsert_edge(conn, source=civ_id, target="civilt_forsvar", relation="REGIONAL_INDELNING_AV", weight=2.2)
        upsert_edge(conn, source=civ_id, target="sfs_2022_524", relation="REGLERAS_AV", weight=1.4)

        for county_name in civ.get("counties", []):
            county_id = f"county_{_slugify(county_name)}"
            is_lead = county_name.replace("s län", " län") in civ["lead_county_board"] or (
                county_name.split()[0] in civ["lead_county_board"]
            )
            upsert_node(
                conn,
                node_id=county_id,
                node_type="county",
                name=f"Länsstyrelsen / Region i {county_name}",
                short_name=county_name,
                domain="lansstyrelsen.se",
                url="https://www.lansstyrelsen.se",
                description=(
                    f"Högsta civila totalförsvarsmyndighet på länsnivå i {county_name}"
                    + (f" samt civilområdesansvarig länsstyrelse för {civ['name']}." if is_lead else ".")
                ),
                metadata={"county": county_name, "is_civilomrade_lead": is_lead},
            )
            rel = "CIVILOMRADESANSVARIG_FOR" if is_lead else "INGAR_I_CIVILOMRADE"
            upsert_edge(conn, source=county_id, target=civ_id, relation=rel, weight=2.2 if is_lead else 1.4)
            if conn.execute("SELECT 1 FROM nodes WHERE id = 'agency_lansstyrelserna'").fetchone():
                upsert_edge(conn, source=county_id, target="agency_lansstyrelserna", relation="DEL_AV_LANSSTYRELSERNA", weight=1.0)

    for umb in reg_cfg.get("umbrella_and_regions", []):
        umb_id = f"regional_{umb['id']}"
        upsert_node(
            conn,
            node_id=umb_id,
            node_type="regional_umbrella",
            name=umb["name"],
            short_name="SKR (290 kommuner & 21 regioner)",
            domain=umb["domain"],
            url=umb["base_urls"][0],
            description="Företräder Sveriges 290 kommuner och 21 regioner, som utgör basen i det lokala och regionala civila försvaret enligt LEH (2006:544).",
        )
        upsert_edge(conn, source=umb_id, target="civilt_forsvar", relation="SAMORDNAR_KOMMUNER_OCH_REGIONER", weight=2.0)
        upsert_edge(conn, source=umb_id, target="sfs_2006_544", relation="STYRS_AV_LAG", weight=2.0)

    # 7b. Försvarsmaktens 4 Militärregioner & samverkan med civilområdena
    militarregioner = [
        (
            "militarregion_norra",
            "Norra militärregionen (MR N)",
            "MR Norra (Boden)",
            "Regional militär stab med säte i Boden som leder regionala insatser och samverkar med Norra civilområdet.",
            ["civilomrade_norra_civilomradet"],
        ),
        (
            "militarregion_mellersta",
            "Mellersta militärregionen (MR M)",
            "MR Mellersta (Kungsängen)",
            "Regional militär stab som samverkar med Mellersta och Östra civilområdet.",
            ["civilomrade_mellersta_civilomradet", "civilomrade_ostra_civilomradet"],
        ),
        (
            "militarregion_vastra",
            "Västra militärregionen (MR V)",
            "MR Västra (Skövde)",
            "Regional militär stab med säte i Skövde som samverkar med Västra civilområdet och delar av mellersta/sydöstra Sverige.",
            ["civilomrade_vastra_civilomradet"],
        ),
        (
            "militarregion_sodra",
            "Södra militärregionen (MR S)",
            "MR Södra (Revingehed/Lund)",
            "Regional militär stab i Skåne som samverkar med Södra och Sydöstra civilområdet.",
            ["civilomrade_sodra_civilomradet", "civilomrade_sydostra_civilomradet"],
        ),
    ]
    for mr_id, mr_name, mr_short, mr_desc, linked_civs in militarregioner:
        upsert_node(
            conn,
            node_id=mr_id,
            node_type="militarregion",
            name=mr_name,
            short_name=mr_short,
            domain="forsvarsmakten.se",
            url="https://www.forsvarsmakten.se/sv/organisation/militarregioner/",
            description=mr_desc,
        )
        upsert_edge(conn, source=mr_id, target="agency_forsvarsmakten", relation="REGIONAL_STAB_INOM", weight=2.0)
        for civ_target in linked_civs:
            upsert_edge(conn, source=mr_id, target=civ_target, relation="SAMVERKAR_REGIONAL_MED", weight=1.9)

    # 8. Frivilliga försvarsorganisationer (18 FFO) & Näringsliv
    vol_cfg = cfg.get("voluntary_and_private_sector", {})
    portal = vol_cfg.get("voluntary_defense_portal")
    if portal:
        upsert_node(
            conn,
            node_id="ffo_portal",
            node_type="ffo_hub",
            name="De 18 Frivilliga försvarsorganisationerna (FFO)",
            short_name="Frivilligförsvaret (18 FFO)",
            domain=portal["domain"],
            url=f"https://www.{portal['domain']}",
            description="Samlingsnod för de 18 statligt erkända frivilliga försvarsorganisationerna som rekryterar och utbildar frivilliga till både militärt och civilt försvar.",
        )
        upsert_edge(conn, source="ffo_portal", target="militart_forsvar", relation="FORSTARKER_MED_FRIVILLIGA", weight=1.8)
        upsert_edge(conn, source="ffo_portal", target="civilt_forsvar", relation="FORSTARKER_MED_FRIVILLIGA", weight=1.8)

    for ffo in vol_cfg.get("ffo_organizations", []):
        ffo_id = f"ffo_{_slugify(ffo['name'])}"
        upsert_node(
            conn,
            node_id=ffo_id,
            node_type="ffo",
            name=ffo["name"],
            short_name=ffo["name"].split("(")[0].strip(),
            domain=ffo["domain"],
            url=f"https://www.{ffo['domain']}",
            description="Frivillig försvarsorganisation med uppdrag inom Sveriges totalförsvar.",
        )
        upsert_edge(conn, source=ffo_id, target="ffo_portal", relation="INGAR_I_FFO", weight=1.3)

    for biz in vol_cfg.get("business_preparedness", []):
        biz_id = f"biz_{biz['id']}"
        upsert_node(
            conn,
            node_id=biz_id,
            node_type="business_org",
            name=biz["name"],
            short_name=biz["name"].split("(")[0].strip(),
            domain=biz["domain"],
            url=f"https://www.{biz['domain']}",
            description="Näringslivs- och branschaktör med roll i Sveriges försörjningsberedskap.",
        )
        upsert_edge(conn, source=biz_id, target="civilt_forsvar", relation="FORSORJNINGSBEREDSKAP", weight=1.6)
        upsert_edge(conn, source=biz_id, target="sfs_1982_1004", relation="OMFATTAS_AV_LAG", weight=1.5)

    # 9. Campus Totalförsvar & de 37 samverkande lärosätena
    for acad in cfg.get("academia_and_education", []):
        camp_id = f"academia_{acad['id']}"
        upsert_node(
            conn,
            node_id=camp_id,
            node_type="academia_hub",
            name=acad["name"],
            short_name="Campus totalförsvar (37 lärosäten)",
            domain=acad["domain"],
            url="https://campustotalforsvar.se/om-campus-totalforsvar/larosaten-i-samarbetet",
            description="Nationellt strategiskt samarbete mellan 37 svenska universitet och högskolor för utbildning och forskning som stärker totalförsvaret.",
        )
        upsert_edge(conn, source=camp_id, target="totalforsvaret", relation="UTBILDAR_OCH_FORSKAR_FOR", weight=2.0)

        for uni_name in acad.get("participating_universities", []):
            if "Försvarshögskolan" in uni_name and conn.execute("SELECT 1 FROM nodes WHERE id = 'agency_fhs'").fetchone():
                upsert_edge(conn, source="agency_fhs", target=camp_id, relation="SAMVERKAR_I_CAMPUS", weight=1.6)
                continue
            uni_id = f"uni_{_slugify(uni_name)}"
            upsert_node(
                conn,
                node_id=uni_id,
                node_type="university",
                name=uni_name,
                short_name=uni_name,
                domain="campustotalforsvar.se",
                url="https://campustotalforsvar.se/om-campus-totalforsvar/larosaten-i-samarbetet",
                description="Lärosäte som ingår i det nationella samarbetet Campus totalförsvar.",
            )
            upsert_edge(conn, source=uni_id, target=camp_id, relation="SAMVERKAR_I_CAMPUS", weight=1.2)

    conn.commit()
    node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    return {"nodes": node_count, "edges": edge_count}
