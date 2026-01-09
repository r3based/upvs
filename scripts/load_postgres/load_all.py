from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Iterable, List, Tuple

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json


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


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def batch_iter(rows: Iterable[Tuple[object, ...]], batch_size: int) -> Iterable[List[Tuple[object, ...]]]:
    batch: List[Tuple[object, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_pages(cur: psycopg2.extensions.cursor, pages_path: Path, batch_size: int) -> None:
    rows: List[Tuple[object, ...]] = []
    with pages_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                (
                    row.get("page_id"),
                    row.get("url"),
                    row.get("title"),
                    row.get("parent_url"),
                    Json(json.loads(row.get("breadcrumbs_json") or "null")),
                    Json(json.loads(row.get("toc_json") or "null")),
                    row.get("fetched_at") or None,
                    int(row.get("http_status")) if row.get("http_status") else None,
                    row.get("content_hash"),
                )
            )
            if len(rows) >= batch_size:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO pages (
                        page_id, url, title, parent_url, breadcrumbs, toc, fetched_at, http_status, content_hash
                    ) VALUES %s
                    ON CONFLICT (page_id) DO NOTHING
                    """,
                    rows,
                )
                rows = []

    if rows:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO pages (
                page_id, url, title, parent_url, breadcrumbs, toc, fetched_at, http_status, content_hash
            ) VALUES %s
            ON CONFLICT (page_id) DO NOTHING
            """,
            rows,
        )


def load_chunks(cur: psycopg2.extensions.cursor, chunks_path: Path, batch_size: int) -> None:
    def row_iter() -> Iterable[Tuple[object, ...]]:
        for item in read_jsonl(chunks_path):
            yield (
                item.get("chunk_id"),
                item.get("page_id"),
                item.get("chunk_index"),
                item.get("source_order"),
                Json(item.get("section_path") or []),
                item.get("text"),
            )

    for batch in batch_iter(row_iter(), batch_size):
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO text_chunks (
                chunk_id, page_id, chunk_index, source_order, section_path, text
            ) VALUES %s
            ON CONFLICT (chunk_id) DO NOTHING
            """,
            batch,
        )


def load_tables(cur: psycopg2.extensions.cursor, tables_path: Path, batch_size: int) -> None:
    def row_iter() -> Iterable[Tuple[object, ...]]:
        for item in read_jsonl(tables_path):
            yield (
                item.get("table_id"),
                item.get("page_id"),
                item.get("table_index"),
                item.get("source_order"),
                Json(item.get("section_path") or []),
                item.get("caption"),
                Json(item.get("columns") or []),
                Json(item.get("rows") or []),
                item.get("raw_html"),
            )

    for batch in batch_iter(row_iter(), batch_size):
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO tables (
                table_id, page_id, table_index, source_order, section_path, caption, columns, rows, raw_html
            ) VALUES %s
            ON CONFLICT (table_id) DO NOTHING
            """,
            batch,
        )


def load_edges(cur: psycopg2.extensions.cursor, edges_path: Path, batch_size: int) -> None:
    def row_iter() -> Iterable[Tuple[object, ...]]:
        with edges_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield (row.get("from_url"), row.get("to_url"))

    for batch in batch_iter(row_iter(), batch_size):
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO edges (from_url, to_url) VALUES %s",
            batch,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузка данных UPVS в Postgres")
    parser.add_argument("--truncate", action="store_true", default=False)
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--batch-size", type=int, default=10000)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    pages_path = data_dir / "pages.csv"
    chunks_path = data_dir / "text_chunks.jsonl"
    tables_path = data_dir / "tables.jsonl"
    edges_path = data_dir / "edges.csv"

    database_url = os.getenv("DATABASE_URL", "postgresql://upvs:upvs@localhost:5432/upvs")
    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_SQL)
                if args.truncate:
                    cur.execute("TRUNCATE edges, tables, text_chunks, pages")
        with conn:
            with conn.cursor() as cur:
                if pages_path.exists():
                    print("Загрузка pages.csv...")
                    load_pages(cur, pages_path, args.batch_size)
                if chunks_path.exists():
                    print("Загрузка text_chunks.jsonl...")
                    load_chunks(cur, chunks_path, args.batch_size)
                if tables_path.exists():
                    print("Загрузка tables.jsonl...")
                    load_tables(cur, tables_path, args.batch_size)
                if edges_path.exists():
                    print("Загрузка edges.csv...")
                    load_edges(cur, edges_path, args.batch_size)
        print("Готово.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
