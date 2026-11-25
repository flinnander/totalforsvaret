"""Inhämtning av lagar och riksdagsdokument via Riksdagens Öppna Data API.

Hämtar fulltext för centrala totalförsvarsförfattningar (SFS) och kontrollerar
allt innehåll mot ScopeGuard (SECURITY_AND_SCOPE.md) före indexering i SQLite FTS5.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import sqlite3
from bs4 import BeautifulSoup
import httpx

from .db import upsert_document_with_chunks
from .scope_guard import ScopeGuard
from .seed import CORE_SFS_DESCRIPTIONS


RIKSDAGEN_DOCLIST_URL = "https://data.riksdagen.se/dokumentlista/"


def _html_to_chunks(html_or_text: str, fallback_heading: str) -> list[tuple[str, str]]:
    """Delar upp SFS-lagtext eller HTML i sökbara paragraf-/rubrikavsnitt."""
    if "<" in html_or_text and ">" in html_or_text:
        soup = BeautifulSoup(html_or_text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        raw_text = soup.get_text("\n")
    else:
        raw_text = html_or_text

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return []

    chunks: list[tuple[str, str]] = []
    current_heading = fallback_heading
    buffer: list[str] = []
    current_len = 0

    section_pattern = re.compile(r"^(\d+\s*kap\.|\d+\s*[a-z]?\s*§|Bilaga\b|Övergångsbestämmelser)", re.IGNORECASE)

    for line in lines:
        is_heading = bool(section_pattern.match(line)) and len(line) < 120
        if is_heading and current_len >= 350:
            chunks.append((current_heading, "\n".join(buffer)))
            buffer = []
            current_len = 0
            current_heading = line
        elif is_heading and not buffer:
            current_heading = line

        buffer.append(line)
        current_len += len(line)

        if current_len >= 1400:
            chunks.append((current_heading, "\n".join(buffer)))
            buffer = []
            current_len = 0

    if buffer:
        chunks.append((current_heading, "\n".join(buffer)))

    return chunks


def ingest_core_sfs_from_riksdagen(
    conn: sqlite3.Connection,
    scope_guard: ScopeGuard,
    timeout_s: float = 20.0,
) -> dict[str, int]:
    """Hämtar centrala SFS-författningar från data.riksdagen.se och indexerar dem."""
    fetched_docs = 0
    total_chunks = 0
    skipped = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    headers = {
        "User-Agent": "Totalforsvaret-OpenRAG-Bot/1.0 (+https://github.com/flinnander/totalforsvaret)",
    }

    with httpx.Client(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
        for sfs_num, (fallback_title, fallback_desc) in CORE_SFS_DESCRIPTIONS.items():
            rm_year, nr_num = sfs_num.split(":", 1)
            try:
                resp = client.get(
                    RIKSDAGEN_DOCLIST_URL,
                    params={
                        "doktyp": "sfs",
                        "rm": rm_year,
                        "nr": nr_num,
                        "utformat": "json",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
                docs = payload.get("dokumentlista", {}).get("dokument", [])
                if isinstance(docs, dict):
                    docs = [docs]

                if not docs:
                    total_chunks += upsert_document_with_chunks(
                        conn,
                        doc_id=f"sfs:{sfs_num}",
                        doc_type="sfs",
                        title=fallback_title,
                        subtitle=f"SFS {sfs_num}",
                        year=int(rm_year),
                        source_url=f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/_sfs-{sfs_num.replace(':', '-')}/",
                        actor_id="riksdagen",
                        fetched_at=now_iso,
                        metadata={"sfs": sfs_num, "fallback": True},
                        chunks=[(f"Översikt SFS {sfs_num}", fallback_desc)],
                    )
                    fetched_docs += 1
                    continue

                doc = docs[0]
                dok_id = doc.get("dok_id", f"sfs-{sfs_num.replace(':', '-')}")
                title = doc.get("titel") or fallback_title
                subtitle = doc.get("undertitel") or f"SFS {sfs_num}"
                doc_url_text = doc.get("dokument_url_text") or doc.get("dokument_url_html") or ""
                if doc_url_text.startswith("//"):
                    doc_url_text = "https:" + doc_url_text

                allowed, _reason = scope_guard.is_allowed(title=title, url=doc_url_text, summary=subtitle)
                if not allowed:
                    skipped += 1
                    continue

                body_text = fallback_desc
                if doc_url_text:
                    text_resp = client.get(doc_url_text)
                    if text_resp.status_code == 200 and text_resp.text.strip():
                        body_text = text_resp.text

                chunks = _html_to_chunks(body_text, fallback_heading=f"SFS {sfs_num}")
                if not chunks:
                    chunks = [(f"SFS {sfs_num}", fallback_desc)]

                page_url = (
                    f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/"
                    f"_{dok_id.lower()}/"
                )
                total_chunks += upsert_document_with_chunks(
                    conn,
                    doc_id=f"sfs:{sfs_num}",
                    doc_type="sfs",
                    title=title,
                    subtitle=subtitle,
                    year=int(sfs_num.split(":")[0]),
                    source_url=page_url,
                    actor_id="riksdagen",
                    fetched_at=now_iso,
                    metadata={"sfs": sfs_num, "dok_id": dok_id},
                    chunks=chunks,
                )
                fetched_docs += 1
            except Exception:
                # Robust fallback om nätverket skulle tima ut för en enskild författning
                total_chunks += upsert_document_with_chunks(
                    conn,
                    doc_id=f"sfs:{sfs_num}",
                    doc_type="sfs",
                    title=fallback_title,
                    subtitle=f"SFS {sfs_num}",
                    year=int(sfs_num.split(":")[0]),
                    source_url=f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/_sfs-{sfs_num.replace(':', '-')}/",
                    actor_id="riksdagen",
                    fetched_at=now_iso,
                    metadata={"sfs": sfs_num, "fallback": True},
                    chunks=[(f"Översikt SFS {sfs_num}", fallback_desc)],
                )
                fetched_docs += 1

    conn.commit()
    return {"documents": fetched_docs, "chunks": total_chunks, "skipped": skipped}
