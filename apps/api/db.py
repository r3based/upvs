from contextlib import contextmanager
from typing import Generator, Iterable, List, Optional, Tuple
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from .config import Settings


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS pages (
    page_id TEXT PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    parent_url TEXT,
    breadcrumbs JSONB,
    toc JSONB,
    fetched_at TIMESTAMPTZ,
    http_status INT,
    content_hash TEXT
);

CREATE TABLE IF NOT EXISTS text_chunks (
    chunk_id TEXT PRIMARY KEY,
    page_id TEXT REFERENCES pages(page_id),
    chunk_index INT,
    source_order INT,
    section_path JSONB,
    text TEXT
);

CREATE TABLE IF NOT EXISTS tables (
    table_id TEXT PRIMARY KEY,
    page_id TEXT REFERENCES pages(page_id),
    table_index INT,
    source_order INT,
    section_path JSONB,
    caption TEXT,
    columns JSONB,
    rows JSONB,
    raw_html TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    from_url TEXT,
    to_url TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_chunks_page_id ON text_chunks(page_id);
CREATE INDEX IF NOT EXISTS idx_tables_page_id ON tables(page_id);
CREATE INDEX IF NOT EXISTS idx_edges_from_url ON edges(from_url);
CREATE INDEX IF NOT EXISTS idx_edges_to_url ON edges(to_url);
"""


class Database:
    def __init__(self, settings: Settings) -> None:
        self._pool = SimpleConnectionPool(1, 5, settings.database_url)

    @contextmanager
    def connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def init_schema(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
            conn.commit()

    def fetch_one(self, query: str, params: Tuple[object, ...]) -> Optional[dict]:
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else None

    def fetch_all(self, query: str, params: Tuple[object, ...]) -> List[dict]:
        with self.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def fetch_all_with_connection(
        self, conn: psycopg2.extensions.connection, query: str, params: Tuple[object, ...]
    ) -> List[dict]:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def fetch_all_iter(
        self, conn: psycopg2.extensions.connection, query: str, params: Tuple[object, ...]
    ) -> Iterable[dict]:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            for row in cur:
                yield dict(row)
