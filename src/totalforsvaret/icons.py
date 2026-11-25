"""Hämtar och cachar heraldiska vapen, sigill och logotyper lokalt till web/public/icons/.

Prioritetsordning:
1. Officiella svenska heraldiska vapen (Wikidata P94 'vapenbild' – länsvapen, riksvapen, myndigheters vapen)
2. Officiella logotyper/sigill på Wikimedia Commons (Wikidata P154 / Wikipedia pageimages)
3. Domänens webbplatsikon (128px PNG) för organisationer som saknar bild på Wikimedia
4. Skarp genererad heraldisk SVG-sköld för konceptuella noder (t.ex. lagrum SFS & beredskapssektorer)

Alla bilder lagras lokalt i web/public/icons/ så att WebGL (3D), Canvas (2D) och Karta
kan ladda texturer i 60 FPS helt utan CORS-problem eller externa beroenden vid körning.
"""

from __future__ import annotations

import html
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote
import httpx


WIKI_TITLE_OVERRIDES: dict[str, str] = {
    "totalforsvaret": "Sveriges riksvapen",
    "militart_forsvar": "Sveriges försvarsmakt",
    "civilt_forsvar": "Myndigheten för civilt försvar",
    "riksdagen": "Sveriges riksdag",
    "regeringen": "Regeringskansliet",
    "esv_regleringsbrev": "Ekonomistyrningsverket",
    "riksbanken": "Sveriges riksbank",
    "nato_alliansen": "Nato",
    "nato_ncrs": "Nato",
    "nato_hns": "Nato",
    "nato_ndpp": "Nato",
    "agency_forsvarsmakten": "Sveriges försvarsmakt",
    "militarregion_norra": "Norra militärregionen",
    "militarregion_mellersta": "Mellersta militärregionen",
    "militarregion_vastra": "Västra militärregionen",
    "militarregion_sodra": "Södra militärregionen",
    "agency_mcf": "Myndigheten för civilt försvar",
    "agency_mpf": "Myndigheten för psykologiskt försvar",
    "agency_mtfa": "Myndigheten för totalförsvarsanalys",
    "agency_foi": "Totalförsvarets forskningsinstitut",
    "agency_fhs": "Försvarshögskolan",
    "agency_pliktverket": "Totalförsvarets plikt- och prövningsverk",
    "agency_fmv": "Försvarets materielverk",
    "agency_fra_ncsc": "Försvarets radioanstalt",
    "agency_fortifikationsverket": "Fortifikationsverket",
    "agency_kustbevakningen": "Kustbevakningen",
    "agency_sakerhetspolisen": "Säkerhetspolisen",
    "agency_polismyndigheten": "Polismyndigheten",
    "agency_svenska_kraftnat": "Svenska kraftnät",
    "agency_pts": "Post- och telestyrelsen",
    "agency_energimyndigheten": "Statens energimyndighet",
    "agency_digg": "Myndigheten för digital förvaltning",
    "agency_sgu": "Sveriges geologiska undersökning",
    "agency_sva": "Statens veterinärmedicinska anstalt",
    "agency_smhi": "SMHI",
    "agency_luftfartsverket": "Luftfartsverket",
    "agency_lansstyrelserna": "Länsstyrelse",
    "regional_skr": "Sveriges Kommuner och Regioner",
    # Länsvapen för alla 21 län
    "county_norrbottens_lan": "Norrbottens läns vapen",
    "county_vasterbottens_lan": "Västerbottens läns vapen",
    "county_jamtlands_lan": "Jämtlands läns vapen",
    "county_vasternorrlands_lan": "Västernorrlands läns vapen",
    "county_gavleborgs_lan": "Gävleborgs läns vapen",
    "county_dalarnas_lan": "Dalarnas läns vapen",
    "county_varmlands_lan": "Värmlands läns vapen",
    "county_orebro_lan": "Örebro läns vapen",
    "county_vastmanlands_lan": "Västmanlands läns vapen",
    "county_uppsala_lan": "Uppsala läns vapen",
    "county_sodermanlands_lan": "Södermanlands läns vapen",
    "county_stockholms_lan": "Stockholms läns vapen",
    "county_gotlands_lan": "Gotlands läns vapen",
    "county_ostergotlands_lan": "Östergötlands läns vapen",
    "county_jonkopings_lan": "Jönköpings läns vapen",
    "county_kalmar_lan": "Kalmar läns vapen",
    "county_vastra_gotalands_lan": "Västra Götalands läns vapen",
    "county_hallands_lan": "Hallands läns vapen",
    "county_kronobergs_lan": "Kronobergs läns vapen",
    "county_blekinge_lan": "Blekinge läns vapen",
    "county_skane_lan": "Skåne läns vapen",
    # Civilområden får sin civilområdesansvariga länsstyrelses länsvapen
    "civilomrade_norra_civilomradet": "Norrbottens läns vapen",
    "civilomrade_mellersta_civilomradet": "Örebro läns vapen",
    "civilomrade_ostra_civilomradet": "Stockholms läns vapen",
    "civilomrade_sydostra_civilomradet": "Östergötlands läns vapen",
    "civilomrade_vastra_civilomradet": "Västra Götalands läns vapen",
    "civilomrade_sodra_civilomradet": "Skåne läns vapen",
}


SECTOR_GLYPHS: dict[str, str] = {
    "sector_ekonomisk_sakerhet": "KR",
    "sector_elektroniska_kommunikationer_och_post": "TEL",
    "sector_energiforsorjning": "EL",
    "sector_finansiella_tjanster": "FIN",
    "sector_forsorjning_av_grunddata": "DATA",
    "sector_halsa_vard_och_omsorg": "VÅRD",
    "sector_industri_byggande_och_handel": "IND",
    "sector_livsmedelsforsorjning_och_dricksvatten": "MAT",
    "sector_ordning_och_sakerhet": "ORD",
    "sector_raddningstjanst_och_skydd_av_civilbefolkningen": "RÄDD",
    "sector_transporter": "TRP",
    "sector_utrikeshandel": "EXP",
}


def _make_heraldic_shield_svg(label: str, bg_hex: str, border_hex: str = "#fbbf24") -> str:
    safe_label = html.escape(label[:6].upper())
    font_size = 34 if len(safe_label) <= 3 else (26 if len(safe_label) <= 4 else 21)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 148" width="128" height="148">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{bg_hex}"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <path d="M16 14 H112 V72 C112 108 64 136 64 136 C64 136 16 108 16 72 Z"
        fill="url(#g)" stroke="{border_hex}" stroke-width="6" stroke-linejoin="round"/>
  <path d="M40 34 L48 22 L56 32 L64 20 L72 32 L80 22 L88 34 Z" fill="#fbbf24" opacity="0.95"/>
  <text x="64" y="86" text-anchor="middle" fill="#ffffff"
        font-family="Inter, Segoe UI, Arial, sans-serif" font-weight="800" font-size="{font_size}">{safe_label}</text>
</svg>"""


def _initials(name: str) -> str:
    words = [w for w in name.replace("(", " ").replace(")", " ").replace("-", " ").split() if w[0:1].isalnum()]
    stop = {"och", "för", "i", "av", "om", "statens", "myndigheten", "svenska", "sveriges", "lag", "förordning"}
    sig = [w for w in words if w.lower() not in stop] or words
    if len(sig) == 1:
        return sig[0][:3].upper()
    return "".join(w[0] for w in sig[:3]).upper()


def _is_clean_emblem_filename(name_or_url: str) -> bool:
    """Filtrerar bort byggnads- och landskapsfoton (.jpg) så vi bara behåller vapen, sigill och logotyper."""
    low = name_or_url.lower()
    if ".svg" in low:
        return True
    emblem_keywords = ("vapen", "logo", "coat", "arms", "seal", "sigill", "emblem", "flag", "symbol", "crest", "shield")
    return any(k in low for k in emblem_keywords)


def _existing_cached_icon(icons_dir: Path, node_id: str) -> str | None:
    for ext in ("png", "svg", "jpg", "ico", "webp"):
        candidate = icons_dir / f"{node_id}.{ext}"
        if candidate.exists() and candidate.stat().st_size > 80:
            return f"./icons/{candidate.name}"
    return None


def sync_node_icons(
    conn: sqlite3.Connection,
    icons_dir: Path,
    color_by_type: dict[str, str],
    refresh: bool = False,
) -> dict[str, str]:
    """Säkerställer att varje nod i kunskapsgrafen har en lokal ikon i web/public/icons/."""
    icons_dir.mkdir(parents=True, exist_ok=True)
    rows = conn.execute("SELECT id, type, name, short_name, domain FROM nodes").fetchall()

    icon_map: dict[str, str] = {}
    to_resolve: list[sqlite3.Row] = []

    for r in rows:
        nid = r["id"]
        if not refresh:
            cached = _existing_cached_icon(icons_dir, nid)
            if cached:
                icon_map[nid] = cached
                continue
        to_resolve.append(r)

    if not to_resolve:
        return icon_map

    headers = {
        "User-Agent": "TotalforsvaretOpenGraph/1.0 (+https://github.com/flinnander/totalforsvaret; educational open source)",
    }

    with httpx.Client(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # 1. Direkt genererade sköldar för SFS-lagrum och beredskapssektorer samt NATO-grundkrav
        wiki_candidates: list[tuple[sqlite3.Row, str]] = []
        for r in to_resolve:
            nid = r["id"]
            ntype = r["type"]
            bg = color_by_type.get(ntype, "#1e293b")

            if ntype == "law":
                sfs_code = (r["short_name"] or "SFS").replace("SFS ", "§")
                svg = _make_heraldic_shield_svg(sfs_code[:6], "#be123c", "#fda4af")
                out = icons_dir / f"{nid}.svg"
                out.write_text(svg, encoding="utf-8")
                icon_map[nid] = f"./icons/{out.name}"
                continue

            if ntype == "sector":
                glyph = SECTOR_GLYPHS.get(nid, _initials(r["short_name"] or r["name"]))
                svg = _make_heraldic_shield_svg(glyph, "#047857", "#6ee7b7")
                out = icons_dir / f"{nid}.svg"
                out.write_text(svg, encoding="utf-8")
                icon_map[nid] = f"./icons/{out.name}"
                continue

            if ntype == "nato_requirement":
                num = nid.split("_")[-1][:3].upper()
                if "." in (r["short_name"] or ""):
                    num = "N" + (r["short_name"] or "1").split(".")[0].strip()
                svg = _make_heraldic_shield_svg(num, "#0369a1", "#bae6fd")
                out = icons_dir / f"{nid}.svg"
                out.write_text(svg, encoding="utf-8")
                icon_map[nid] = f"./icons/{out.name}"
                continue

            # Bestäm Wikipedia-titel att slå upp
            title = WIKI_TITLE_OVERRIDES.get(nid)
            if not title:
                clean_name = (r["short_name"] or r["name"]).split("(")[0].strip()
                title = clean_name
            wiki_candidates.append((r, title))

        # 2. Batch-uppslagning mot sv.wikipedia.org (max 40 titlar åt gången)
        title_to_thumb: dict[str, str] = {}
        title_to_qid: dict[str, str] = {}
        unique_titles = sorted({t for _, t in wiki_candidates if t})

        for i in range(0, len(unique_titles), 40):
            batch = unique_titles[i : i + 40]
            try:
                resp = client.get(
                    "https://sv.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "redirects": 1,
                        "titles": "|".join(batch),
                        "prop": "pageimages|pageprops",
                        "piprop": "thumbnail",
                        "pithumbsize": 256,
                        "format": "json",
                    },
                )
                if resp.status_code == 200:
                    qdata = resp.json().get("query", {})
                    redirect_map: dict[str, str] = {}
                    for rd in qdata.get("redirects", []):
                        redirect_map[rd["from"]] = rd["to"]
                    norm_map: dict[str, str] = {}
                    for nm in qdata.get("normalized", []):
                        norm_map[nm["from"]] = nm["to"]

                    page_by_title: dict[str, dict] = {}
                    for p in qdata.get("pages", {}).values():
                        if "title" in p:
                            page_by_title[p["title"]] = p

                    for orig_t in batch:
                        resolved = norm_map.get(orig_t, orig_t)
                        resolved = redirect_map.get(resolved, resolved)
                        p = page_by_title.get(resolved) or page_by_title.get(orig_t)
                        if not p or "missing" in p:
                            continue
                        thumb = p.get("thumbnail", {}).get("source")
                        qid = p.get("pageprops", {}).get("wikibase_item")
                        if thumb and _is_clean_emblem_filename(thumb):
                            title_to_thumb[orig_t] = thumb
                        if qid:
                            title_to_qid[orig_t] = qid
            except Exception:
                pass

        # 3. Slå upp Wikidata P94 (heraldiskt vapen!) i första hand och P154 (logotyp) i andra hand
        qid_to_commons_file: dict[str, str] = {}
        all_qids = sorted(set(title_to_qid.values()))
        for i in range(0, len(all_qids), 45):
            batch_qids = all_qids[i : i + 45]
            try:
                wresp = client.get(
                    "https://www.wikidata.org/w/api.php",
                    params={
                        "action": "wbgetentities",
                        "ids": "|".join(batch_qids),
                        "props": "claims",
                        "format": "json",
                    },
                )
                if wresp.status_code == 200:
                    entities = wresp.json().get("entities", {})
                    for qid, ent in entities.items():
                        claims = ent.get("claims", {})
                        chosen_file: str | None = None
                        # Prioritera P94 (heraldiskt vapen / coat of arms) över P154 (logotyp)!
                        for prop_id in ("P94", "P154"):
                            prop_claims = claims.get(prop_id, [])
                            if prop_claims:
                                snak = prop_claims[0].get("mainsnak", {})
                                val = snak.get("datavalue", {}).get("value")
                                if isinstance(val, str) and val.strip():
                                    if prop_id == "P94" or _is_clean_emblem_filename(val):
                                        chosen_file = val.strip()
                                        break
                        if chosen_file:
                            qid_to_commons_file[qid] = chosen_file
            except Exception:
                pass

        # 4. Ladda ner ikonbilden (med delad URL-cache i minnet så t.ex. alla NATO-noder går blixtsnabbt)
        url_bytes_cache: dict[str, tuple[bytes, str]] = {}

        def fetch_image_bytes(img_url: str) -> tuple[bytes, str] | None:
            if img_url in url_bytes_cache:
                return url_bytes_cache[img_url]
            for attempt in range(2):
                try:
                    ir = client.get(img_url)
                    if ir.status_code == 200 and len(ir.content) > 120:
                        ctype = ir.headers.get("content-type", "").lower()
                        if "svg" in ctype:
                            ext = "svg"
                        elif "jpeg" in ctype or "jpg" in ctype:
                            ext = "jpg"
                        elif "webp" in ctype:
                            ext = "webp"
                        else:
                            ext = "png"
                        url_bytes_cache[img_url] = (ir.content, ext)
                        return ir.content, ext
                    if ir.status_code == 429:
                        time.sleep(0.4 * (attempt + 1))
                except Exception:
                    pass
            return None

        for r, wtitle in wiki_candidates:
            nid = r["id"]
            ntype = r["type"]
            domain = (r["domain"] or "").split("/")[0].strip()

            candidate_urls: list[str] = []
            qid = title_to_qid.get(wtitle)
            if qid and qid in qid_to_commons_file:
                fname = qid_to_commons_file[qid].replace(" ", "_")
                candidate_urls.append(
                    f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(fname)}?width=256"
                )
            if wtitle in title_to_thumb:
                candidate_urls.append(title_to_thumb[wtitle])
            if domain and "." in domain:
                candidate_urls.append(f"https://www.google.com/s2/favicons?domain={domain}&sz=128")

            saved = False
            for curl in candidate_urls:
                fetched = fetch_image_bytes(curl)
                if fetched:
                    raw_bytes, ext = fetched
                    out_file = icons_dir / f"{nid}.{ext}"
                    out_file.write_bytes(raw_bytes)
                    icon_map[nid] = f"./icons/{out_file.name}"
                    saved = True
                    break

            if not saved:
                bg = color_by_type.get(ntype, "#1e293b")
                svg = _make_heraldic_shield_svg(_initials(r["short_name"] or r["name"]), bg)
                out_file = icons_dir / f"{nid}.svg"
                out_file.write_text(svg, encoding="utf-8")
                icon_map[nid] = f"./icons/{out_file.name}"

    return icon_map
