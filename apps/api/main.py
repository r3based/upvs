from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import get_settings
from .db import Database

settings = get_settings()
logger = logging.getLogger("upvs.api")
logging.basicConfig(level=logging.INFO)

# Bearer token аутентификация
security = HTTPBearer()

app = FastAPI(
    title="UPVS API",
    description="""
# API для доступа к справочнику UPVS

Этот API предоставляет доступ к справочнику **UPVS** (Укрупненные Показатели Восстановительной Стоимости).

## 🔐 Аутентификация

Все эндпоинты (кроме `/health`) требуют Bearer token аутентификации.

Добавьте заголовок: `Authorization: Bearer YOUR_API_KEY`

## 📖 Как использовать

1. **Получите структуру** справочника через `/api/tree`
2. **Найдите нужный раздел** по названию через `/api/tree/search`
3. **Получите содержимое страницы** через `/api/page/{page_id}`
4. **Найдите таблицу** по названию через `/api/tables/search`
5. **Получите данные таблицы** через `/api/table/{table_id}`

## 🎯 Рекомендуемый workflow для ChatGPT

1. Сначала получите дерево или найдите нужный раздел
2. Затем запросите конкретную страницу или таблицу
3. Используйте полученные данные для ответа пользователю
""",
    version="2.0.0",
    servers=[
        {"url": "http://localhost:8000", "description": "Локальный сервер"},
        {"url": "https://your-domain.com", "description": "Продакшн сервер"}
    ],
    contact={
        "name": "UPVS API Support"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database(settings)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> bool:
    """Проверка Bearer токена"""
    if credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный API ключ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


@app.on_event("startup")
def on_startup() -> None:
    db.init_schema()
    logger.info("UPVS API запущен. API Key требуется для всех эндпоинтов (кроме /health и /docs)")


@app.get("/health", tags=["System"])
def health() -> Dict[str, str]:
    """Проверка состояния API (не требует аутентификации)"""
    return {"status": "ok"}


@app.get("/openapi.json", tags=["System"])
def get_openapi_json():
    """
    Получить OpenAPI schema для ChatGPT Actions.
    
    Используйте этот эндпоинт для получения актуальной схемы API,
    которую можно импортировать в ChatGPT Actions.
    """
    return JSONResponse(content=app.openapi())


# ========== ЭНДПОИНТЫ ДЛЯ CHATGPT ==========

@app.get("/api/tree", tags=["Navigation"], summary="Получить дерево всех страниц")
def get_full_tree(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Возвращает полное дерево страниц справочника UPVS.
    
    Структура дерева:
    - Корневые страницы (без родителя)
    - Каждая страница содержит список дочерних страниц
    - Для каждой страницы: page_id, url, title, children[]
    
    Используйте этот эндпоинт, чтобы понять структуру справочника и найти нужные разделы.
    """
    verify_token(credentials)
    
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
    for page in all_pages:
        url = page["url"]
        pages_by_url[url] = {
            "page_id": page["page_id"],
            "url": page["url"],
            "title": page["title"],
            "children": []
        }
    
    # Строим дерево
    root_pages = []
    for page in all_pages:
        parent_url = page.get("parent_url")
        node = pages_by_url[page["url"]]
        
        if parent_url and parent_url in pages_by_url:
            parent = pages_by_url[parent_url]
            parent["children"].append(node)
        else:
            root_pages.append(node)
    
    # Сортируем детей по title
    def sort_children(node: Dict[str, object]) -> None:
        if node.get("children"):
            node["children"].sort(key=lambda x: x.get("title", "") or "")
            for child in node["children"]:
                sort_children(child)
    
    for root in root_pages:
        sort_children(root)
    
    return {"tree": root_pages, "total_pages": len(all_pages)}


@app.get("/api/tree/search", tags=["Navigation"], summary="Найти страницы по названию")
def search_tree(
    query: str = Field(..., description="Поисковый запрос по названию страницы"),
    limit: int = Field(20, ge=1, le=100, description="Максимальное количество результатов"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Поиск страниц по названию (регистронезависимый).
    
    Возвращает список страниц с информацией о родителе и детях для каждой найденной страницы.
    """
    verify_token(credentials)
    
    rows = db.fetch_all(
        """
        SELECT page_id, url, title, parent_url
        FROM pages
        WHERE title ILIKE %s
        ORDER BY title
        LIMIT %s
        """,
        (f"%{query}%", limit),
    )
    
    results = []
    for row in rows:
        # Получаем информацию о родителе
        parent = None
        if row.get("parent_url"):
            parent = db.fetch_one(
                "SELECT page_id, url, title FROM pages WHERE url = %s",
                (row["parent_url"],),
            )
        
        # Получаем дочерние страницы
        children = db.fetch_all(
            """
            SELECT page_id, url, title
            FROM pages
            WHERE parent_url = %s
            ORDER BY title
            LIMIT 10
            """,
            (row["url"],),
        )
        
        results.append({
            "page_id": row["page_id"],
            "url": row["url"],
            "title": row["title"],
            "parent": parent,
            "children": children,
        })
    
    return {"results": results, "count": len(results)}


@app.get("/api/page/{page_id}", tags=["Content"], summary="Получить всю информацию о странице")
def get_page_full(
    page_id: str = Field(..., description="ID страницы из дерева"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Возвращает ВСЮ информацию о странице:
    - Метаданные страницы (title, url, breadcrumbs, toc)
    - Все текстовые блоки (в порядке появления)
    - Все таблицы с данными (columns, rows, caption)
    
    Используйте этот эндпоинт, когда нужно получить полное содержимое конкретной страницы.
    """
    verify_token(credentials)
    
    page = db.fetch_one(
        """
        SELECT page_id, url, title, parent_url, breadcrumbs, toc, fetched_at
        FROM pages
        WHERE page_id = %s
        """,
        (page_id,),
    )
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    
    # Получаем все текстовые блоки
    text_blocks = db.fetch_all(
        """
        SELECT chunk_id, source_order, section_path, text
        FROM text_chunks
        WHERE page_id = %s
        ORDER BY source_order
        """,
        (page_id,),
    )
    
    # Получаем все таблицы
    tables = db.fetch_all(
        """
        SELECT table_id, source_order, section_path, caption, columns, rows
        FROM tables
        WHERE page_id = %s
        ORDER BY source_order
        """,
        (page_id,),
    )
    
    # Объединяем все в единый упорядоченный список контента
    content = []
    for block in text_blocks:
        content.append({
            "type": "text",
            "order": block["source_order"],
            "section_path": block["section_path"],
            "text": block["text"],
        })
    
    for table in tables:
        content.append({
            "type": "table",
            "order": table["source_order"],
            "section_path": table["section_path"],
            "table_id": table["table_id"],
            "caption": table["caption"],
            "columns": table["columns"],
            "rows": table["rows"],
        })
    
    # Сортируем по порядку
    content.sort(key=lambda x: x["order"])
    
    return {
        "page": {
            "page_id": page["page_id"],
            "url": page["url"],
            "title": page["title"],
            "parent_url": page["parent_url"],
            "breadcrumbs": page["breadcrumbs"],
            "toc": page["toc"],
        },
        "content": content,
        "statistics": {
            "text_blocks": len(text_blocks),
            "tables": len(tables),
            "total_items": len(content),
        }
    }


@app.get("/api/tables/list", tags=["Tables"], summary="Список всех таблиц с названиями")
def list_all_tables(
    limit: int = Field(100, ge=1, le=500, description="Максимальное количество таблиц"),
    offset: int = Field(0, ge=0, description="Смещение для пагинации"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Возвращает список всех таблиц в справочнике с их названиями и страницами.
    
    Для каждой таблицы возвращается:
    - table_id: уникальный ID таблицы
    - caption: название/заголовок таблицы
    - page_title: название страницы, на которой находится таблица
    - page_id: ID страницы
    
    Используйте этот эндпоинт, чтобы найти нужную таблицу по названию,
    затем используйте /api/table/{table_id} для получения данных.
    """
    verify_token(credentials)
    
    tables = db.fetch_all(
        """
        SELECT t.table_id, t.caption, t.page_id, p.title as page_title, p.url
        FROM tables t
        JOIN pages p ON t.page_id = p.page_id
        WHERE t.caption IS NOT NULL AND t.caption != ''
        ORDER BY p.title, t.source_order
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
    
    # Получаем общее количество таблиц
    total = db.fetch_one(
        "SELECT COUNT(*) as count FROM tables WHERE caption IS NOT NULL AND caption != ''",
        (),
    )
    
    return {
        "tables": tables,
        "count": len(tables),
        "total": total["count"] if total else 0,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/tables/search", tags=["Tables"], summary="Поиск таблиц по названию")
def search_tables(
    query: str = Field(..., description="Поисковый запрос по названию таблицы"),
    limit: int = Field(20, ge=1, le=100, description="Максимальное количество результатов"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Поиск таблиц по названию (регистронезависимый).
    
    Возвращает список таблиц, содержащих указанный текст в названии.
    Для получения полных данных таблицы используйте /api/table/{table_id}
    """
    verify_token(credentials)
    
    tables = db.fetch_all(
        """
        SELECT t.table_id, t.caption, t.page_id, p.title as page_title, p.url
        FROM tables t
        JOIN pages p ON t.page_id = p.page_id
        WHERE t.caption ILIKE %s
        ORDER BY p.title, t.source_order
        LIMIT %s
        """,
        (f"%{query}%", limit),
    )
    
    return {
        "tables": tables,
        "count": len(tables),
    }


@app.get("/api/table/{table_id}", tags=["Tables"], summary="Получить данные таблицы")
def get_table(
    table_id: str = Field(..., description="ID таблицы из списка таблиц"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Возвращает полные данные конкретной таблицы:
    - caption: название таблицы
    - columns: список названий колонок
    - rows: массив строк с данными
    - section_path: путь к разделу на странице
    - page_info: информация о странице, на которой находится таблица
    
    Используйте этот эндпоинт после того, как нашли нужную таблицу через поиск.
    """
    verify_token(credentials)
    
    table = db.fetch_one(
        """
        SELECT table_id, page_id, caption, columns, rows, section_path, source_order
        FROM tables
        WHERE table_id = %s
        """,
        (table_id,),
    )
    
    if not table:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    
    # Получаем информацию о странице
    page = db.fetch_one(
        "SELECT page_id, url, title FROM pages WHERE page_id = %s",
        (table["page_id"],),
    )
    
    return {
        "table_id": table["table_id"],
        "caption": table["caption"],
        "columns": table["columns"],
        "rows": table["rows"],
        "section_path": table["section_path"],
        "page": page if page else None,
    }


@app.get("/api/page/{page_id}/tables", tags=["Tables"], summary="Получить все таблицы страницы")
def get_page_tables(
    page_id: str = Field(..., description="ID страницы"),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, object]:
    """
    Возвращает все таблицы, которые находятся на конкретной странице.
    
    Полезно, когда вы знаете, на какой странице находится нужная информация,
    и хотите получить все таблицы с этой страницы.
    """
    verify_token(credentials)
    
    page = db.fetch_one(
        "SELECT page_id, url, title FROM pages WHERE page_id = %s",
        (page_id,),
    )
    if not page:
        raise HTTPException(status_code=404, detail="Страница не найдена")
    
    tables = db.fetch_all(
        """
        SELECT table_id, caption, columns, rows, section_path, source_order
        FROM tables
        WHERE page_id = %s
        ORDER BY source_order
        """,
        (page_id,),
    )
    
    return {
        "page": page,
        "tables": tables,
        "count": len(tables),
    }
