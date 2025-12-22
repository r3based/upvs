# UPVS: веб-вьювер + RAG

Монорепозиторий для работы с уже собранными данными UPVS Online. Содержит:

- **Frontend (Next.js)**: статический просмотр бандлов + режим работы через API.
- **Backend (FastAPI)**: Postgres, FAISS поиск, контекст, RAG через vLLM.
- **Скрипты** для подготовки данных, загрузки в Postgres и сборки FAISS.

> Важно: краулер не реализован. Используются файлы из `data/raw`.

## Структура

```
repo/
  apps/
    api/
    web/
  scripts/
    prepare_front_data/
    load_postgres/
    build_faiss/
    tests/
  data/
    raw/
    derived/
  docker/
    docker-compose.yml
  README.md
  .env.example
```

## Быстрый старт (Docker Compose)

1. Подготовьте `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

2. Убедитесь, что файлы лежат в `data/raw`:

```
pages.csv
text_chunks.jsonl
tables.jsonl
edges.csv
```

3. Соберите фронт-бандлы:

```bash
python scripts/prepare_front_data/build_page_bundles.py
```

4. Поднимите Postgres:

```bash
docker compose -f docker/docker-compose.yml up -d postgres
```

5. Загрузите данные в Postgres:

```bash
DATABASE_URL=postgresql://upvs:upvs@localhost:5432/upvs \
  python scripts/load_postgres/load_all.py --truncate
```

6. Соберите FAISS:

```bash
EMBEDDINGS_PROVIDER=st \
  python scripts/build_faiss/build_faiss.py --batch-size 32
```

7. Запустите сервисы:

```bash
docker compose -f docker/docker-compose.yml up --build
```

8. Проверьте smoke-тесты:

```bash
API_BASE=http://localhost:8000 python scripts/tests/smoke_rag.py
```

## Режимы фронта

- **API режим** (по умолчанию): `NEXT_PUBLIC_MODE=api`.
- **Static режим**: `NEXT_PUBLIC_MODE=static` — Next.js читает локальные бандлы из `data/derived` через встроенные API-роуты.

## Переменные окружения

Основные параметры находятся в `.env.example`.

- `DATABASE_URL` — строка подключения к Postgres.
- `FAISS_INDEX_PATH`, `FAISS_MAP_PATH` — файлы индекса и mapping.
- `EMBEDDINGS_PROVIDER` — `st` или `http`.
- `VLLM_URL`, `VLLM_MODEL` — параметры OpenAI-compatible endpoint.

## Примечания по данным

- `text_chunks` и `tables` остаются раздельными сущностями.
- Связь обеспечивается через `page_id` и `source_order`.

## Troubleshooting

- **FAISS не найден**: убедитесь, что выполнен `build_faiss.py`, а пути в `.env` совпадают.
- **Большие файлы**: используйте батчи (по умолчанию 10k для Postgres, 32 для эмбеддингов).
- **Colab экспорт**: проверьте кодировки и отсутствие BOM; JSONL должен быть построчно корректным JSON.
