from __future__ import annotations

import json
import logging
import time
from typing import Dict, List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .db import Database
from .faiss_store import FaissStore

settings = get_settings()
logger = logging.getLogger("upvs.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="UPVS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database(settings)
faiss_store = FaissStore(settings)


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=50)


class ContextRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=50)
    tables_window: int = Field(default=2, ge=0, le=10)


class RagRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=50)
    tables_window: int = Field(default=2, ge=0, le=10)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=800, ge=64, le=2048)


@app.on_event("startup")
def on_startup() -> None:
    db.init_schema()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/pages")
def list_pages(query: str = "", limit: int = 20, offset: int = 0) -> Dict[str, object]:
    if query:
        rows = db.fetch_all(
            """
            SELECT page_id, url, title, fetched_at
            FROM pages
            WHERE title ILIKE %s
            ORDER BY fetched_at DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (f"%{query}%", limit, offset),
        )
    else:
        rows = db.fetch_all(
            """
            SELECT page_id, url, title, fetched_at
            FROM pages
            ORDER BY fetched_at DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
    return {"items": rows}


@app.get("/pages/{page_id}")
def get_page(page_id: str) -> Dict[str, object]:
    page = db.fetch_one(
        """
        SELECT page_id, url, title, parent_url, breadcrumbs, toc, fetched_at, http_status, content_hash
        FROM pages
        WHERE page_id = %s
        """,
        (page_id,),
    )
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    return page


@app.get("/pages/{page_id}/blocks")
def get_page_blocks(page_id: str) -> Dict[str, object]:
    page = db.fetch_one("SELECT page_id, url, title FROM pages WHERE page_id = %s", (page_id,))
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    text_blocks = db.fetch_all(
        """
        SELECT chunk_id, source_order, section_path, text
        FROM text_chunks
        WHERE page_id = %s
        """,
        (page_id,),
    )
    table_blocks = db.fetch_all(
        """
        SELECT table_id, source_order, section_path, caption, columns, rows
        FROM tables
        WHERE page_id = %s
        """,
        (page_id,),
    )
    blocks: List[Dict[str, object]] = []
    for row in text_blocks:
        blocks.append(
            {
                "kind": "text",
                "chunk_id": row["chunk_id"],
                "source_order": row["source_order"],
                "section_path": row["section_path"],
                "text": row["text"],
            }
        )
    for row in table_blocks:
        blocks.append(
            {
                "kind": "table",
                "table_id": row["table_id"],
                "source_order": row["source_order"],
                "section_path": row["section_path"],
                "caption": row["caption"],
                "columns": row["columns"],
                "rows": row["rows"],
            }
        )
    blocks.sort(key=lambda item: item["source_order"])
    return {"page": page, "blocks": blocks}


@app.get("/pages/{page_id}/neighbors")
def get_neighbors(page_id: str, depth: int = 1, limit: int = 20) -> Dict[str, object]:
    page = db.fetch_one("SELECT url FROM pages WHERE page_id = %s", (page_id,))
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    url = page["url"]
    outgoing = db.fetch_all(
        "SELECT to_url FROM edges WHERE from_url = %s LIMIT %s", (url, limit)
    )
    incoming = db.fetch_all(
        "SELECT from_url FROM edges WHERE to_url = %s LIMIT %s", (url, limit)
    )
    urls = {row["to_url"] for row in outgoing} | {row["from_url"] for row in incoming}
    resolved = []
    if urls:
        resolved = db.fetch_all(
            "SELECT page_id, url, title FROM pages WHERE url = ANY(%s)", (list(urls),)
        )
    return {
        "depth": depth,
        "outgoing": outgoing,
        "incoming": incoming,
        "resolved": resolved,
    }


@app.post("/search")
def search(req: SearchRequest) -> Dict[str, object]:
    start = time.perf_counter()
    try:
        hits = faiss_store.search(req.query, req.top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    duration = time.perf_counter() - start
    logger.info("search duration=%.3fs query=%s", duration, req.query)

    page_ids = {hit.page_id for hit in hits}
    titles: Dict[str, str] = {}
    if page_ids:
        rows = db.fetch_all(
            "SELECT page_id, title FROM pages WHERE page_id = ANY(%s)", (list(page_ids),)
        )
        titles = {row["page_id"]: row.get("title") for row in rows}

    result = []
    for hit in hits:
        result.append(
            {
                "chunk_id": hit.chunk_id,
                "page_id": hit.page_id,
                "url": hit.url,
                "score": hit.score,
                "section_path": hit.section_path,
                "text_preview": hit.text_preview,
                "title": titles.get(hit.page_id),
            }
        )
    return {"hits": result, "duration": duration}


def _collect_tables(page_id: str, source_order: int, window: int) -> List[Dict[str, object]]:
    tables = db.fetch_all(
        """
        SELECT table_id, source_order, caption, columns, rows
        FROM tables
        WHERE page_id = %s
        """,
        (page_id,),
    )
    if not tables:
        return []
    if window == 0:
        nearest = min(tables, key=lambda t: abs(t["source_order"] - source_order))
        return [nearest]
    return [t for t in tables if abs(t["source_order"] - source_order) <= window]


@app.post("/context")
def context(req: ContextRequest) -> Dict[str, object]:
    try:
        hits = faiss_store.search(req.query, req.top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    sources = []
    for hit in hits:
        chunk = db.fetch_one(
            """
            SELECT chunk_id, page_id, section_path, text, source_order
            FROM text_chunks
            WHERE chunk_id = %s
            """,
            (hit.chunk_id,),
        )
        if not chunk:
            continue
        page = db.fetch_one(
            "SELECT page_id, url, title FROM pages WHERE page_id = %s", (chunk["page_id"],)
        )
        tables = _collect_tables(chunk["page_id"], chunk["source_order"], req.tables_window)
        sources.append(
            {
                "page_id": chunk["page_id"],
                "url": page.get("url") if page else hit.url,
                "title": page.get("title") if page else None,
                "chunk_id": chunk["chunk_id"],
                "score": hit.score,
                "section_path": chunk["section_path"],
                "text": chunk["text"],
                "tables": tables,
            }
        )
    return {"sources": sources}


def _format_tables(tables: List[Dict[str, object]]) -> str:
    parts: List[str] = []
    for table in tables:
        caption = table.get("caption") or "Таблица"
        columns = table.get("columns") or []
        rows = table.get("rows") or []
        parts.append(f"### {caption}")
        if columns and len(columns) <= 8 and len(rows) <= 12:
            header = "|" + "|".join(columns) + "|"
            sep = "|" + "|".join(["---"] * len(columns)) + "|"
            parts.append(header)
            parts.append(sep)
            for row in rows:
                parts.append("|" + "|".join(str(cell) for cell in row) + "|")
        else:
            parts.append(json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False))
    return "\n".join(parts)


@app.post("/rag")
def rag(req: RagRequest) -> Dict[str, object]:
    retrieval_start = time.perf_counter()
    context_payload = context(ContextRequest(query=req.query, top_k=req.top_k, tables_window=req.tables_window))
    retrieval_duration = time.perf_counter() - retrieval_start
    logger.info("context duration=%.3fs query=%s", retrieval_duration, req.query)

    sources = context_payload["sources"]
    if not sources:
        return {"answer": "Недостаточно данных в источниках.", "sources": []}

    system_prompt = (
        "Ты помощник по учебнику UPVS. Отвечай строго по предоставленным источникам. "
        "Если информации недостаточно, скажи об этом прямо."
    )
    chunks_text = []
    for idx, source in enumerate(sources, start=1):
        tables_text = _format_tables(source.get("tables", []))
        chunk = (
            f"Источник {idx}\n"
            f"URL: {source.get('url')}\n"
            f"Раздел: {' / '.join(source.get('section_path') or [])}\n"
            f"Текст: {source.get('text')}\n"
        )
        if tables_text:
            chunk += f"\nТаблицы:\n{tables_text}\n"
        chunks_text.append(chunk)

    user_prompt = (
        f"Вопрос: {req.query}\n\n" + "\n".join(chunks_text)
    )

    gen_start = time.perf_counter()
    response = requests.post(
        f"{settings.vllm_url}/chat/completions",
        json={
            "model": settings.vllm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Ошибка vLLM: {response.text}")
    payload = response.json()
    answer = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    generation_duration = time.perf_counter() - gen_start
    logger.info(
        "rag duration retrieval=%.3fs generation=%.3fs query=%s",
        retrieval_duration,
        generation_duration,
        req.query,
    )

    return {
        "answer": answer.strip(),
        "sources": sources,
        "retrieval_duration": retrieval_duration,
        "generation_duration": generation_duration,
    }
