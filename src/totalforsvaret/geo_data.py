"""Källgrupper (Source Groups) och administrativa tätortskoordinater för kartvisualisering.

SÄKERHETSSKYDDSPRINCIP (se SECURITY_AND_SCOPE.md):
Samtliga koordinater nedan anger UTESLUTANDE offentliga stadscentrum / kommunala sätesorter
(residensstäder, universitetsorter och myndigheters officiella säteskommuner).
Inga anläggningsadresser, skyddsobjekt eller operativa platser förekommer.
"""

from __future__ import annotations

import math
from typing import Any


SOURCE_GROUPS: dict[str, dict[str, Any]] = {
    "styrning_lagrum": {
        "id": "styrning_lagrum",
        "title": "1. Styrning, Regleringsbrev & Lagrum (SFS)",
        "shortTitle": "Styrning & Lagrum",
        "description": "Totalförsvarets huvudpelare, Riksdagen, Regeringen, regleringsbrev (ESV), Riksbanken och centrala SFS-lagar.",
        "color": "#f59e0b",
        "defaultEnabled": True,
    },
    "nato_allians": {
        "id": "nato_allians",
        "title": "2. NATO, NCRS/CRM & Resilienskrav",
        "shortTitle": "NATO & Alliansramverk",
        "description": "NATO, krishanteringssystemet NCRS/NRS, Värdlandsstöd (HNS), NDPP och de 7 grundkraven (Artikel 3).",
        "color": "#38bdf8",
        "defaultEnabled": True,
    },
    "militart_och_karnmyndigheter": {
        "id": "militart_och_karnmyndigheter",
        "title": "3. Militärt försvar & Försvarsmyndigheter",
        "shortTitle": "Militärt & Försvarsmyndigheter",
        "description": "Försvarsmakten, de 4 militärregionerna, MCF (f.d. MSB), MPF, FOI, Pliktverket, FMV, FRA m.fl.",
        "color": "#fbbf24",
        "defaultEnabled": True,
    },
    "beredskapssektorer": {
        "id": "beredskapssektorer",
        "title": "4. De 12 Beredskapssektorerna & Myndigheter",
        "shortTitle": "12 Beredskapssektorer",
        "description": "Sveriges 12 beredskapssektorer, sektorsansvariga myndigheter och samtliga ~67 beredskapsmyndigheter.",
        "color": "#10b981",
        "defaultEnabled": True,
    },
    "geografi_civilomraden": {
        "id": "geografi_civilomraden",
        "title": "5. Regionalt: 6 Civilområden, 21 Län & SKR",
        "shortTitle": "6 Civilområden & 21 Län",
        "description": "De 6 civilområdena, civilområdesansvariga länsstyrelser, samtliga 21 län/regioner och SKR (290 kommuner).",
        "color": "#a855f7",
        "defaultEnabled": True,
    },
    "frivilliga_och_naringsliv": {
        "id": "frivilliga_och_naringsliv",
        "title": "6. Frivilligförsvar (18 FFO) & Näringsliv",
        "shortTitle": "18 FFO & Näringsliv",
        "description": "De 18 frivilliga försvarsorganisationerna samt näringslivets branschaktörer inom försörjningsberedskap.",
        "color": "#fb923c",
        "defaultEnabled": True,
    },
    "akademi_campus": {
        "id": "akademi_campus",
        "title": "7. Campus Totalförsvar (37 Lärosäten)",
        "shortTitle": "Campus Totalförsvar (37 st)",
        "description": "Nationell utbildnings- och forskningssamverkan mellan 37 svenska universitet och högskolor.",
        "color": "#22d3ee",
        "defaultEnabled": True,
    },
}


# Offentliga stadscentrumkoordinater (lat, lon) för svenska sätesorter + Bryssel (NATO HQ)
CITY_CENTERS: dict[str, tuple[float, float]] = {
    "Stockholm": (59.3293, 18.0686),
    "Solna": (59.3600, 18.0009),
    "Sundbyberg": (59.3613, 17.9711),
    "Kungsängen": (59.4792, 17.7519),
    "Huddinge": (59.2363, 17.9822),
    "Uppsala": (59.8586, 17.6389),
    "Nyköping": (58.7528, 17.0092),
    "Eskilstuna": (59.3712, 16.5098),
    "Linköping": (58.4108, 15.6214),
    "Norrköping": (58.5877, 16.1924),
    "Jönköping": (57.7826, 14.1618),
    "Växjö": (56.8790, 14.8059),
    "Kalmar": (56.6634, 16.3568),
    "Visby": (57.6348, 18.2948),
    "Karlskrona": (56.1612, 15.5869),
    "Kristianstad": (56.0294, 14.1567),
    "Malmö": (55.6050, 13.0038),
    "Lund": (55.7047, 13.1910),
    "Halmstad": (56.6744, 12.8578),
    "Göteborg": (57.7089, 11.9746),
    "Borås": (57.7210, 12.9401),
    "Trollhättan": (58.2837, 12.2886),
    "Skövde": (58.3898, 13.8461),
    "Karlstad": (59.3793, 13.5036),
    "Örebro": (59.2753, 15.2134),
    "Västerås": (59.6099, 16.5448),
    "Falun": (60.6065, 15.6355),
    "Borlänge": (60.4843, 15.4340),
    "Gävle": (60.6749, 17.1413),
    "Sundsvall": (62.3908, 17.3069),
    "Härnösand": (62.6323, 17.9409),
    "Östersund": (63.1767, 14.6361),
    "Umeå": (63.8258, 20.2630),
    "Luleå": (65.5848, 22.1567),
    "Boden": (65.8251, 21.6887),
    "Bryssel (NATO HQ)": (50.8779, 4.4257),
}


COUNTY_TO_RESIDENSSTAD: dict[str, str] = {
    "county_norrbottens_lan": "Luleå",
    "county_vasterbottens_lan": "Umeå",
    "county_jamtlands_lan": "Östersund",
    "county_vasternorrlands_lan": "Härnösand",
    "county_gavleborgs_lan": "Gävle",
    "county_dalarnas_lan": "Falun",
    "county_varmlands_lan": "Karlstad",
    "county_orebro_lan": "Örebro",
    "county_vastmanlands_lan": "Västerås",
    "county_uppsala_lan": "Uppsala",
    "county_sodermanlands_lan": "Nyköping",
    "county_stockholms_lan": "Stockholm",
    "county_gotlands_lan": "Visby",
    "county_ostergotlands_lan": "Linköping",
    "county_jonkopings_lan": "Jönköping",
    "county_kalmar_lan": "Kalmar",
    "county_vastra_gotalands_lan": "Göteborg",
    "county_hallands_lan": "Halmstad",
    "county_kronobergs_lan": "Växjö",
    "county_blekinge_lan": "Karlskrona",
    "county_skane_lan": "Malmö",
}


NODE_TO_CITY: dict[str, str] = {
    # Statsledning & Styrning
    "totalforsvaret": "Stockholm",
    "militart_forsvar": "Stockholm",
    "civilt_forsvar": "Stockholm",
    "riksdagen": "Stockholm",
    "regeringen": "Stockholm",
    "esv_regleringsbrev": "Stockholm",
    "riksbanken": "Stockholm",
    "regional_skr": "Stockholm",
    # NATO
    "nato_alliansen": "Bryssel (NATO HQ)",
    # Civilområden (kansli vid respektive civilområdesansvarig länsstyrelse)
    "civilomrade_norra_civilomradet": "Luleå",
    "civilomrade_mellersta_civilomradet": "Örebro",
    "civilomrade_ostra_civilomradet": "Stockholm",
    "civilomrade_sydostra_civilomradet": "Linköping",
    "civilomrade_vastra_civilomradet": "Göteborg",
    "civilomrade_sodra_civilomradet": "Malmö",
    # Militärregioner
    "militarregion_norra": "Boden",
    "militarregion_mellersta": "Kungsängen",
    "militarregion_vastra": "Skövde",
    "militarregion_sodra": "Lund",
    # Försvars- och beredskapsmyndigheters officiella sätesorter
    "agency_forsvarsmakten": "Stockholm",
    "agency_mcf": "Karlstad",
    "agency_mpf": "Karlstad",
    "agency_pliktverket": "Karlstad",
    "agency_mtfa": "Stockholm",
    "agency_foi": "Stockholm",
    "agency_fhs": "Stockholm",
    "agency_fmv": "Stockholm",
    "agency_fra_ncsc": "Stockholm",
    "agency_fortifikationsverket": "Eskilstuna",
    "agency_energimyndigheten": "Eskilstuna",
    "agency_energimarknadsinspektionen": "Eskilstuna",
    "agency_trafikverket": "Borlänge",
    "agency_sjofartsverket": "Norrköping",
    "agency_luftfartsverket": "Norrköping",
    "agency_transportstyrelsen": "Norrköping",
    "agency_smhi": "Norrköping",
    "agency_migrationsverket": "Norrköping",
    "agency_kriminalvarden": "Norrköping",
    "agency_livsmedelsverket": "Uppsala",
    "agency_lakemedelsverket": "Uppsala",
    "agency_sva": "Uppsala",
    "agency_sgu": "Uppsala",
    "agency_jordbruksverket": "Jönköping",
    "agency_domstolsverket": "Jönköping",
    "agency_kustbevakningen": "Karlskrona",
    "agency_boverket": "Karlskrona",
    "agency_ehalsomyndigheten": "Kalmar",
    "agency_bolagsverket": "Sundsvall",
    "agency_digg": "Sundsvall",
    "agency_lantmateriet": "Gävle",
    "agency_statens_servicecenter": "Gävle",
    "agency_svenska_kraftnat": "Sundbyberg",
    "agency_skatteverket": "Solna",
    "agency_arbetsformedlingen": "Solna",
    "agency_folkhalsomyndigheten": "Solna",
    "agency_skolverket": "Solna",
    "agency_stralsakerhetsmyndigheten": "Solna",
    "agency_pts": "Stockholm",
    "agency_socialstyrelsen": "Stockholm",
    "agency_polismyndigheten": "Stockholm",
    "agency_sakerhetspolisen": "Solna",
    "agency_finansinspektionen": "Stockholm",
    "agency_forsakringskassan": "Stockholm",
    "agency_pensionsmyndigheten": "Stockholm",
    "agency_riksgalden": "Stockholm",
    "agency_utbetalningsmyndigheten": "Stockholm",
    "agency_tillvaxtverket": "Stockholm",
    "agency_kommerskollegium": "Stockholm",
    "agency_tullverket": "Stockholm",
    "agency_aklagarmyndigheten": "Stockholm",
    "agency_naturvardsverket": "Stockholm",
    "agency_riksarkivet": "Stockholm",
    "agency_riksantikvarieambetet": "Visby",
    # Campus totalförsvar & 37 lärosäten
    "academia_campus_totalforsvar": "Stockholm",
    "uni_blekinge_tekniska_hogskola": "Karlskrona",
    "uni_chalmers_tekniska_hogskola": "Göteborg",
    "uni_goteborgs_universitet": "Göteborg",
    "uni_gymnastik_och_idrottshogskolan_gih": "Stockholm",
    "uni_handelshogskolan_i_stockholm": "Stockholm",
    "uni_hogskolan_dalarna": "Falun",
    "uni_hogskolan_i_boras": "Borås",
    "uni_hogskolan_i_gavle": "Gävle",
    "uni_hogskolan_i_halmstad": "Halmstad",
    "uni_hogskolan_i_skovde": "Skövde",
    "uni_hogskolan_kristianstad": "Kristianstad",
    "uni_hogskolan_vast": "Trollhättan",
    "uni_jonkoping_university": "Jönköping",
    "uni_karlstads_universitet": "Karlstad",
    "uni_karolinska_institutet": "Solna",
    "uni_konstfack": "Stockholm",
    "uni_kungl_konsthogskolan": "Stockholm",
    "uni_kungl_musikhogskolan": "Stockholm",
    "uni_kungliga_tekniska_hogskolan_kth": "Stockholm",
    "uni_linkopings_universitet": "Linköping",
    "uni_linneuniversitetet": "Växjö",
    "uni_lulea_tekniska_universitet": "Luleå",
    "uni_lunds_universitet": "Lund",
    "uni_malmo_universitet": "Malmö",
    "uni_marie_cederschiold_hogskola": "Stockholm",
    "uni_mittuniversitetet": "Sundsvall",
    "uni_malardalens_universitet": "Västerås",
    "uni_roda_korsets_hogskola": "Huddinge",
    "uni_sophiahemmet_hogskola": "Stockholm",
    "uni_stockholms_konstnarliga_hogskola": "Stockholm",
    "uni_stockholms_universitet": "Stockholm",
    "uni_sveriges_lantbruksuniversitet_slu": "Uppsala",
    "uni_sodertorns_hogskola": "Huddinge",
    "uni_umea_universitet": "Umeå",
    "uni_uppsala_universitet": "Uppsala",
    "uni_orebro_universitet": "Örebro",
    # FFO-nav & Näringsliv
    "ffo_portal": "Stockholm",
    "biz_svenskt_naringsliv": "Stockholm",
    "biz_energiforetagen": "Stockholm",
    "biz_livsmedelsforetagen": "Stockholm",
}


def resolve_source_group(node_id: str, node_type: str, metadata: dict[str, Any]) -> str:
    """Bestämmer vilken av de 7 källgrupperna en nod tillhör."""
    if node_type in {"governance", "law"} or node_id in {"totalforsvaret", "riksbanken"}:
        return "styrning_lagrum"
    if node_type in {"nato_framework", "nato_mechanism", "nato_requirement"}:
        return "nato_allians"
    if node_type in {"militarregion"} or node_id == "militart_forsvar":
        return "militart_och_karnmyndigheter"
    if node_id == "civilt_forsvar" or node_type == "sector":
        return "beredskapssektorer"
    if node_type == "agency":
        if metadata.get("category") == "defense_and_core" and not metadata.get("is_preparedness_agency"):
            return "militart_och_karnmyndigheter"
        if node_id in {"agency_forsvarsmakten", "agency_fmv", "agency_fra_ncsc", "agency_fortifikationsverket", "agency_foi", "agency_fhs", "agency_pliktverket", "agency_mtfa"}:
            return "militart_och_karnmyndigheter"
        return "beredskapssektorer"
    if node_type in {"civilomrade", "county", "regional_umbrella"}:
        return "geografi_civilomraden"
    if node_type in {"ffo_hub", "ffo", "business_org"}:
        return "frivilliga_och_naringsliv"
    if node_type in {"academia_hub", "university"}:
        return "akademi_campus"
    return "styrning_lagrum"


def resolve_city_coordinates(node_id: str, city_occurrence_counter: dict[str, int]) -> dict[str, Any] | None:
    """Returnerar administrativa tätortskoordinater med en liten deterministisk spiral-offset
    om flera aktörer har säte i samma stad, så att markörer inte täcker varandra på kartan."""
    city = COUNTY_TO_RESIDENSSTAD.get(node_id) or NODE_TO_CITY.get(node_id)
    if not city or city not in CITY_CENTERS:
        return None

    base_lat, base_lon = CITY_CENTERS[city]
    idx = city_occurrence_counter.get(city, 0)
    city_occurrence_counter[city] = idx + 1

    if idx == 0:
        lat, lon = base_lat, base_lon
    else:
        # Gyllene vinkeln-spiral (~600 m–2.5 km radie beroende på antal aktörer i staden)
        angle = idx * 2.399963229728653
        radius_deg = 0.0065 * math.sqrt(idx)
        lat = round(base_lat + radius_deg * math.sin(angle), 5)
        lon = round(base_lon + (radius_deg * 1.75) * math.cos(angle), 5)

    return {
        "city": city,
        "lat": lat,
        "lon": lon,
        "precision": "administrative_municipality_center",
    }
