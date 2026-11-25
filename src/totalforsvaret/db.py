"""SQLite-databas med Kunskapsgraf (noder & kanter) + FTS5 BM25-sökindex."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "totalforsvaret.db"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    domain TEXT,
    url TEXT,
    description TEXT NOT NULL DEFAULT '',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE,
    UNIQUE(source, target, relation)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT NOT NULL DEFAULT '',
    year INTEGER,
    source_url TEXT NOT NULL,
    actor_id TEXT,
    fetched_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    section_heading TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    doc_id UNINDEXED,
    doc_type,
    title,
    section_heading,
    content,
    tokenize = 'unicode61 remove_diacritics 0'
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection, reset_graph: bool = False) -> None:
    if reset_graph:
        conn.executescript(
            """
            DROP TABLE IF EXISTS edges;
            DROP TABLE IF EXISTS nodes;
            """
        )
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def upsert_node(
    conn: sqlite3.Connection,
    *,
    node_id: str,
    node_type: str,
    name: str,
    short_name: str | None = None,
    domain: str | None = None,
    url: str | None = None,
    description: str = "",
    aliases: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO nodes (id, type, name, short_name, domain, url, description, aliases_json, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            type = excluded.type,
            name = excluded.name,
            short_name = COALESCE(excluded.short_name, nodes.short_name),
            domain = COALESCE(excluded.domain, nodes.domain),
            url = COALESCE(excluded.url, nodes.url),
            description = CASE WHEN excluded.description != '' THEN excluded.description ELSE nodes.description END,
            aliases_json = CASE WHEN excluded.aliases_json != '[]' THEN excluded.aliases_json ELSE nodes.aliases_json END,
            metadata_json = excluded.metadata_json
        """,
        (
            node_id,
            node_type,
            name,
            short_name,
            domain,
            url or (f"https://www.{domain}" if domain and not domain.startswith("http") else domain),
            description,
            json.dumps(aliases or [], ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def upsert_edge(
    conn: sqlite3.Connection,
    *,
    source: str,
    target: str,
    relation: str,
    weight: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO edges (source, target, relation, weight, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source, target, relation) DO UPDATE SET
            weight = excluded.weight,
            metadata_json = excluded.metadata_json
        """,
        (
            source,
            target,
            relation,
            weight,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def upsert_document_with_chunks(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    doc_type: str,
    title: str,
    subtitle: str = "",
    year: int | None = None,
    source_url: str,
    actor_id: str | None = None,
    fetched_at: str,
    metadata: dict[str, Any] | None = None,
    chunks: list[tuple[str, str]],
) -> int:
    """Lagrar ett dokument och dess textavsnitt i både tabell och FTS5-index."""
    conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
    conn.execute(
        """
        INSERT INTO documents (doc_id, doc_type, title, subtitle, year, source_url, actor_id, fetched_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            doc_type = excluded.doc_type,
            title = excluded.title,
            subtitle = excluded.subtitle,
            year = excluded.year,
            source_url = excluded.source_url,
            actor_id = excluded.actor_id,
            fetched_at = excluded.fetched_at,
            metadata_json = excluded.metadata_json
        """,
        (
            doc_id,
            doc_type,
            title,
            subtitle,
            year,
            source_url,
            actor_id,
            fetched_at,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    count = 0
    for idx, (heading, text) in enumerate(chunks):
        cleaned = text.strip()
        if not cleaned:
            continue
        chunk_id = f"{doc_id}::chunk_{idx:04d}"
        conn.execute(
            """
            INSERT INTO document_chunks (chunk_id, doc_id, section_heading, content, chunk_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chunk_id, doc_id, heading, cleaned, idx),
        )
        conn.execute(
            """
            INSERT INTO chunks_fts (chunk_id, doc_id, doc_type, title, section_heading, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, doc_id, doc_type, title, heading, cleaned),
        )
        count += 1
    return count
