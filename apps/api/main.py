from __future__ import annotations

import json
import logging
import re
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


@app.get("/navigation/tree")
def get_navigation_tree() -> Dict[str, object]:
    """Возвращает дерево навигации на основе parent_url"""
    all_pages = db.fetch_all(
        """
        SELECT page_id, url, title, parent_url
        FROM pages
        WHERE title IS NOT NULL
        ORDER BY url
        """,
        (),
    )
    
    # Создаем словарь всех страниц
    pages_by_url: Dict[str, Dict[str, object]] = {}
    pages_by_id: Dict[str, Dict[str, object]] = {}
    for page in all_pages:
        url = page["url"]
        page_id = page["page_id"]
        pages_by_url[url] = page
        pages_by_id[page_id] = page
        page["children"] = []
    
    # Строим дерево
    root_pages = []
    for page in all_pages:
        parent_url = page.get("parent_url")
        if parent_url and parent_url in pages_by_url:
            parent = pages_by_url[parent_url]
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(page)
        else:
            root_pages.append(page)
    
    # Сортируем детей по title
    def sort_children(node: Dict[str, object]) -> None:
        if "children" in node and node["children"]:
            node["children"].sort(key=lambda x: x.get("title", "") or "")
            for child in node["children"]:
                sort_children(child)
    
    for root in root_pages:
        sort_children(root)
    
    return {"tree": root_pages}


@app.get("/navigation/page/{page_id}")
def get_page_navigation(page_id: str) -> Dict[str, object]:
    """Возвращает навигацию для конкретной страницы: родители, соседи, дети"""
    page = db.fetch_one(
        """
        SELECT page_id, url, title, parent_url, breadcrumbs
        FROM pages
        WHERE page_id = %s
        """,
        (page_id,),
    )
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    
    # Получаем родительскую страницу
    parent = None
    if page.get("parent_url"):
        parent = db.fetch_one(
            "SELECT page_id, url, title FROM pages WHERE url = %s",
            (page["parent_url"],),
        )
    
    # Получаем соседние страницы (дети того же родителя)
    siblings = []
    if page.get("parent_url"):
        siblings = db.fetch_all(
            """
            SELECT page_id, url, title
            FROM pages
            WHERE parent_url = %s AND page_id != %s
            ORDER BY title
            """,
            (page["parent_url"], page_id),
        )
    
    # Получаем дочерние страницы
    children = db.fetch_all(
        """
        SELECT page_id, url, title
        FROM pages
        WHERE parent_url = %s
        ORDER BY title
        """,
        (page["url"],),
    )
    
    return {
        "current": {
            "page_id": page["page_id"],
            "url": page["url"],
            "title": page["title"],
        },
        "parent": parent,
        "siblings": siblings,
        "children": children,
    }


def _boost_score_by_keywords(score: float, text: str, title: str, query: str) -> float:
    """Увеличивает score если в тексте или заголовке есть ключевые слова из запроса"""
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    text_lower = (text or "").lower()
    title_lower = (title or "").lower()
    
    # Подсчитываем совпадения ключевых слов
    text_matches = sum(1 for word in query_words if word in text_lower)
    title_matches = sum(1 for word in query_words if word in title_lower)
    
    # Увеличиваем score на основе совпадений
    boost = 0.0
    if title_matches > 0:
        boost += 0.15 * title_matches  # Заголовок важнее
    if text_matches > 0:
        boost += 0.05 * min(text_matches, 3)  # Ограничиваем влияние
    
    return min(score + boost, 1.0)  # Ограничиваем максимумом 1.0


@app.post("/search")
def search(req: SearchRequest) -> Dict[str, object]:
    start = time.perf_counter()
    try:
        # Увеличиваем top_k для семантического поиска, чтобы потом отфильтровать
        semantic_hits = faiss_store.search(req.query, min(req.top_k * 2, 50))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
    page_ids = {hit.page_id for hit in semantic_hits}
    titles: Dict[str, str] = {}
    if page_ids:
        rows = db.fetch_all(
            "SELECT page_id, title FROM pages WHERE page_id = ANY(%s)", (list(page_ids),)
        )
        titles = {row["page_id"]: row.get("title") for row in rows}
    
    # Получаем информацию о таблицах для каждой страницы
    table_captions: Dict[str, List[str]] = {}
    if page_ids:
        table_rows = db.fetch_all(
            """
            SELECT DISTINCT page_id, caption
            FROM tables
            WHERE page_id = ANY(%s) AND caption IS NOT NULL
            """,
            (list(page_ids),),
        )
        for row in table_rows:
            page_id = row["page_id"]
            if page_id not in table_captions:
                table_captions[page_id] = []
            table_captions[page_id].append(row.get("caption", ""))
    
    # Применяем буст на основе ключевых слов
    boosted_hits = []
    for hit in semantic_hits:
        title = titles.get(hit.page_id, "")
        page_tables = " ".join(table_captions.get(hit.page_id, []))
        combined_text = f"{title} {page_tables} {hit.text_preview}"
        
        boosted_score = _boost_score_by_keywords(
            hit.score, combined_text, title, req.query
        )
        boosted_hits.append((boosted_score, hit))
    
    # Сортируем по новому score и берем top_k
    boosted_hits.sort(key=lambda x: x[0], reverse=True)
    top_hits = [hit for _, hit in boosted_hits[:req.top_k]]
    
    duration = time.perf_counter() - start
    logger.info("search duration=%.3fs query=%s", duration, req.query)

    result = []
    for hit in top_hits:
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
        parts.append(f"ТАБЛИЦА: {caption}")
        if columns and len(columns) <= 10 and len(rows) <= 20:
            # Форматируем как markdown таблицу
            header = "| " + " | ".join(str(col) for col in columns) + " |"
            sep = "|" + "|".join([" --- " for _ in columns]) + "|"
            parts.append(header)
            parts.append(sep)
            for row in rows:
                row_str = "| " + " | ".join(str(cell) for cell in row) + " |"
                parts.append(row_str)
        else:
            # Для больших таблиц используем JSON
            parts.append(f"Колонки: {', '.join(str(c) for c in columns)}")
            parts.append(f"Строк данных: {len(rows)}")
            if rows:
                parts.append("Первые строки:")
                for i, row in enumerate(rows[:5]):
                    parts.append(f"  Строка {i+1}: {dict(zip(columns, row))}")
    return "\n".join(parts)


@app.post("/rag")
def rag(req: RagRequest) -> Dict[str, object]:
    try:
        retrieval_start = time.perf_counter()
        context_payload = context(ContextRequest(query=req.query, top_k=req.top_k, tables_window=req.tables_window))
        retrieval_duration = time.perf_counter() - retrieval_start
        logger.info("context duration=%.3fs query=%s", retrieval_duration, req.query)

        sources = context_payload.get("sources", [])
        if not sources:
            return {"answer": "Недостаточно данных в источниках для ответа на вопрос.", "sources": [], "error": None}

        system_prompt = (
            "Ты помощник по справочнику UPVS (Укрупненные Показатели Восстановительной Стоимости). "
            "Твоя задача - отвечать на вопросы, используя ТОЛЬКО информацию из предоставленных источников. "
            "\n\n"
            "КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА (применяются ко ВСЕМ таблицам): "
            "- В источниках может быть НЕСКОЛЬКО похожих таблиц с РАЗНЫМИ номерами\n"
            "- Источники отсортированы по релевантности - ПЕРВЫЙ источник обычно наиболее релевантный\n"
            "- ВНИМАТЕЛЬНО сравнивай название таблицы с вопросом пользователя - они должны ТОЧНО совпадать\n"
            "- Если в вопросе упоминается конкретный тип здания или характеристика, "
            "используй ТОЛЬКО таблицу, которая содержит ЭТИ ЖЕ слова в названии\n"
            "- Если вопрос содержит номер таблицы, используй ТОЛЬКО эту таблицу\n"
            "- НЕ ПУТАЙ разные таблицы - даже если они похожи, они для РАЗНЫХ типов зданий/сооружений\n"
            "- Если вопрос про удельный вес, найди раздел 'Удельные веса' в ПРАВИЛЬНОЙ таблице\n"
            "- Отвечай конкретно, используя ТОЧНЫЕ числа из ПРАВИЛЬНОЙ таблицы\n"
            "- ВСЕГДА указывай номер и название таблицы, из которой взяты данные"
        )
        # Сортируем источники по релевантности (score) - более релевантные первыми
        sorted_sources = sorted(sources, key=lambda x: x.get("score", 0), reverse=True)
        
        chunks_text = []
        for idx, source in enumerate(sorted_sources, start=1):
            tables_text = _format_tables(source.get("tables", []))
            section_path = source.get("section_path") or []
            title = source.get("title") or ""
            score = source.get("score", 0)
            
            chunk = f"\n{'='*60}\nИСТОЧНИК {idx} (релевантность: {score:.3f})\n{'='*60}\n"
            if title:
                # Выделяем название таблицы жирным текстом для лучшей видимости
                chunk += f"📋 НАЗВАНИЕ ТАБЛИЦЫ: {title}\n"
            if section_path:
                chunk += f"📁 РАЗДЕЛ: {' / '.join(section_path)}\n"
            chunk += f"🔗 URL: {source.get('url', '')}\n\n"
            
            # Текст источника
            text = source.get("text", "")
            if text:
                chunk += f"ТЕКСТ:\n{text}\n\n"
            
            # Таблицы
            if tables_text:
                chunk += f"{tables_text}\n"
            
            chunks_text.append(chunk)

        # Анализируем вопрос, чтобы выделить ключевые характеристики для фильтрации
        query_lower = req.query.lower()
        
        # Извлекаем ключевые характеристики из вопроса (универсально для любых таблиц)
        characteristics = []
        if "одноэтаж" in query_lower:
            characteristics.append("одноэтажн")
        if "двухэтаж" in query_lower:
            characteristics.append("двухэтажн")
        if "трехэтаж" in query_lower or "3-этаж" in query_lower:
            characteristics.append("трехэтажн")
        if "без подвала" in query_lower:
            characteristics.append("без подвала")
        if "с подвалом" in query_lower:
            characteristics.append("с подвалом")
        if "таблица" in query_lower:
            # Извлекаем номер таблицы
            table_match = re.search(r'таблица\s*(\d+)', query_lower)
            if table_match:
                characteristics.append(f"таблица {table_match.group(1)}")
        
        # Ищем наиболее релевантный источник
        best_match_idx = None
        if characteristics:
            for idx, source in enumerate(sorted_sources):
                title_lower = (source.get("title") or "").lower()
                text_lower = (source.get("text") or "").lower()
                combined = f"{title_lower} {text_lower}"
                
                # Проверяем, содержит ли источник все ключевые характеристики
                matches = sum(1 for char in characteristics if char in combined)
                if matches == len(characteristics):
                    best_match_idx = idx
                    break
        
        user_prompt = (
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ: {req.query}\n"
        )
        
        if characteristics:
            user_prompt += f"\n🔍 КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ В ВОПРОСЕ: {', '.join(characteristics)}\n"
            if best_match_idx is not None:
                user_prompt += f"✅ НАЙДЕН ТОЧНО СООТВЕТСТВУЮЩИЙ ИСТОЧНИК: Источник {best_match_idx + 1}\n"
            user_prompt += "⚠️ ВАЖНО: Используй ТОЛЬКО таблицу, которая содержит ВСЕ эти характеристики в названии!\n"
        
        user_prompt += (
            f"\nИСПОЛЬЗУЙ СЛЕДУЮЩИЕ ИСТОЧНИКИ ДЛЯ ОТВЕТА (отсортированы по релевантности):\n"
            + "".join(chunks_text) + "\n" + "="*60 + "\n\n"
            "ИНСТРУКЦИИ ПО ВЫБОРУ ПРАВИЛЬНОЙ ТАБЛИЦЫ (применяются ко ВСЕМ таблицам):\n"
            "- Источники отсортированы по релевантности - первый обычно наиболее подходящий\n"
            "- В источниках может быть НЕСКОЛЬКО похожих таблиц с РАЗНЫМИ номерами\n"
            "- ВНИМАТЕЛЬНО сравнивай название таблицы с вопросом - они должны ТОЧНО совпадать\n"
            "- Если в вопросе упоминается тип здания/сооружения, используй ТОЛЬКО таблицу, "
            "которая содержит ЭТИ ЖЕ слова в названии\n"
            "- Если вопрос содержит номер таблицы - используй ТОЛЬКО эту таблицу\n"
            "- НЕ ПУТАЙ разные таблицы - даже похожие таблицы относятся к РАЗНЫМ типам зданий/сооружений\n"
            "- Если вопрос про удельный вес, найди раздел 'Удельные веса' в ПРАВИЛЬНОЙ таблице\n"
            "- Используй ТОЧНЫЕ данные из ПРАВИЛЬНОЙ таблицы - не придумывай числа\n"
            "- В ответе ВСЕГДА указывай номер и название таблицы, из которой взяты данные\n\n"
            "ОТВЕТЬ на вопрос пользователя, используя ТОЛЬКО информацию из ПРАВИЛЬНОЙ таблицы:"
        )

        gen_start = time.perf_counter()
        try:
            # Пытаемся сделать запрос к vLLM
            logger.info("Attempting to connect to vLLM at %s", settings.vllm_url)
            # vLLM требует заголовок Authorization даже если ключ "EMPTY"
            api_key = settings.vllm_api_key if settings.vllm_api_key else "EMPTY"
            headers = {"Authorization": f"Bearer {api_key}"}
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
                headers=headers,
                timeout=120,
            )
            logger.info("vLLM response status: %s", response.status_code)
            response.raise_for_status()
            payload = response.json()
            answer = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not answer:
                answer = "Не удалось получить ответ от модели."
        except requests.exceptions.ConnectionError as exc:
            logger.error("vLLM connection error: %s (URL: %s)", exc, settings.vllm_url)
            error_msg = str(exc)
            answer_parts = [
                "⚠️ Сервис генерации ответов (vLLM) недоступен.",
                f"Попытка подключения к: {settings.vllm_url}",
                "",
                "Найдены следующие релевантные источники:",
                "",
            ]
            for idx, source in enumerate(sources[:3], start=1):
                title = source.get("title") or source.get("url", "")
                section = " / ".join(source.get("section_path") or [])
                answer_parts.append(f"{idx}. {title}")
                if section:
                    answer_parts.append(f"   Раздел: {section}")
                answer_parts.append("")
            return {
                "answer": "\n".join(answer_parts),
                "sources": sources,
                "error": error_msg,
                "retrieval_duration": retrieval_duration,
                "generation_duration": 0.0,
            }
        except requests.exceptions.RequestException as exc:
            logger.error("vLLM request error: %s (URL: %s)", exc, settings.vllm_url)
            error_msg = str(exc)
            answer = f"Ошибка при обращении к модели: {error_msg}"
            return {
                "answer": answer,
                "sources": sources,
                "error": error_msg,
                "retrieval_duration": retrieval_duration,
                "generation_duration": 0.0,
            }
        except Exception as exc:
            logger.error("vLLM processing error: %s", exc)
            return {
                "answer": f"Ошибка при обработке ответа модели: {str(exc)}",
                "sources": sources,
                "error": str(exc),
                "retrieval_duration": retrieval_duration,
                "generation_duration": 0.0,
            }
        
        generation_duration = time.perf_counter() - gen_start
        logger.info(
            "rag duration retrieval=%.3fs generation=%.3fs query=%s",
            retrieval_duration,
            generation_duration,
            req.query,
        )

        return {
            "answer": answer.strip() if answer else "Не удалось получить ответ.",
            "sources": sources,
            "retrieval_duration": retrieval_duration,
            "generation_duration": generation_duration,
            "error": None,
        }
    except Exception as exc:
        logger.error("RAG error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка RAG: {str(exc)}") from exc
