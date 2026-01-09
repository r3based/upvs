# 📂 Структура проекта UPVS v2.0

## 🗂️ Основные директории

```
upvs/
│
├── 📄 START_HERE.md              👈 Начните отсюда!
├── 📄 QUICKSTART.md              ⚡ Быстрый старт (3 минуты)
├── 📄 README.md                  📘 Главная документация
├── 📄 README_CHATGPT.md          📗 Подробное руководство по API
├── 📄 CHATGPT_SETUP.md           🤖 Настройка ChatGPT Actions
├── 📄 PRODUCTION.md              🚀 Деплой в продакшен
├── 📄 CHANGELOG.md               📝 История изменений
├── 📄 SUMMARY.md                 📋 Итоги переделки
├── 📄 PROJECT_STRUCTURE.md       📂 Этот файл
├── 📄 ENV_EXAMPLE.txt            🔧 Пример .env
│
├── 📄 docker-compose.yml         🐳 Docker конфигурация
├── 📄 .gitignore                 🚫 Игнорируемые файлы
│
├── apps/                         💻 Приложения
│   ├── api/                      🔌 FastAPI бекенд
│   │   ├── main.py              ← Основной файл API (эндпоинты)
│   │   ├── config.py            ← Конфигурация (API_KEY, DATABASE_URL)
│   │   ├── db.py                ← Работа с PostgreSQL
│   │   ├── requirements.txt     ← Python зависимости (4 пакета)
│   │   ├── Dockerfile           ← Docker образ для API
│   │   └── __init__.py
│   │
│   └── web/                      🌐 Старый Web фронтенд (не используется)
│
├── scripts/                      🔧 Утилиты и скрипты
│   ├── init_data.py             ← Главный скрипт инициализации
│   ├── load_postgres/           ← Загрузка данных в PostgreSQL
│   │   └── load_all.py
│   ├── build_faiss/             ← Старые скрипты (не используются)
│   ├── prepare_front_data/      ← Старые скрипты (не используются)
│   └── tests/                   ← Тесты (устарели)
│
└── data/                         📊 Данные справочника
    ├── raw/                      📁 Исходные данные (CSV/JSONL)
    │   ├── pages.csv            ← Информация о страницах
    │   ├── text_chunks.jsonl    ← Текстовые блоки
    │   ├── tables.jsonl         ← Таблицы с данными
    │   └── edges.csv            ← Связи между страницами
    │
    └── derived/                  📁 Производные данные (не используются)
```

---

## 📄 Документация (8 файлов)

### Для начинающих:
1. **START_HERE.md** - начните здесь! Общий обзор
2. **QUICKSTART.md** - запуск за 3 минуты

### Для разработчиков:
3. **README.md** - главная документация проекта
4. **README_CHATGPT.md** - подробное руководство по API
5. **PROJECT_STRUCTURE.md** - структура проекта (этот файл)

### Для настройки и деплоя:
6. **CHATGPT_SETUP.md** - настройка ChatGPT Actions
7. **PRODUCTION.md** - деплой в продакшен

### История и изменения:
8. **CHANGELOG.md** - история изменений
9. **SUMMARY.md** - итоги переделки v1→v2

---

## 💻 Основные файлы кода

### API (apps/api/)

| Файл | Строк | Описание |
|------|-------|----------|
| `main.py` | ~400 | Основной файл API с эндпоинтами и аутентификацией |
| `config.py` | ~15 | Конфигурация (API_KEY, DATABASE_URL) |
| `db.py` | ~100 | Работа с PostgreSQL (connection pool, queries) |
| `requirements.txt` | 4 | Python зависимости |
| `Dockerfile` | ~20 | Docker образ для API |

### Скрипты (scripts/)

| Файл | Описание | Используется |
|------|----------|--------------|
| `init_data.py` | Инициализация: загрузка данных в PostgreSQL | ✅ Да |
| `load_postgres/load_all.py` | Загрузка CSV/JSONL в PostgreSQL | ✅ Да |
| `build_faiss/build_faiss.py` | Сборка FAISS индекса | ❌ Нет (удалено) |
| `prepare_front_data/build_page_bundles.py` | Сборка бандлов для фронтенда | ❌ Нет (удалено) |

### Конфигурация

| Файл | Описание |
|------|----------|
| `docker-compose.yml` | Конфигурация Docker (postgres, init, api) |
| `.env` | Переменные окружения (API_KEY) - создать вручную |
| `ENV_EXAMPLE.txt` | Пример .env файла |
| `.gitignore` | Игнорируемые файлы |

---

## 📊 Данные (data/)

### raw/ - Исходные данные

| Файл | Формат | Содержит |
|------|--------|----------|
| `pages.csv` | CSV | Метаданные страниц (url, title, parent_url, etc.) |
| `text_chunks.jsonl` | JSONL | Текстовые блоки страниц |
| `tables.jsonl` | JSONL | Таблицы с данными (caption, columns, rows) |
| `edges.csv` | CSV | Связи между страницами |

### derived/ - Производные данные (не используются в v2.0)

Эта директория содержит старые файлы от v1.x:
- FAISS индексы
- Page bundles для фронтенда
- Кеш embeddings

**В v2.0 эти файлы НЕ используются.**

---

## 🐳 Docker сервисы

### Активные сервисы (3):

```yaml
services:
  postgres:       # PostgreSQL база данных
  init:           # Инициализация: загрузка данных
  api:            # FastAPI REST API
```

### Удалённые сервисы (2):

```yaml
# Было в v1.x:
  vllm:           # ❌ Удалён: локальная LLM
  web:            # ❌ Удалён: Next.js фронтенд
```

---

## 🔧 Конфигурация (.env)

Создайте файл `.env` в корне проекта:

```env
# API ключ для аутентификации
API_KEY=your-secret-key-here

# База данных (опционально, есть дефолт)
DATABASE_URL=postgresql://upvs:upvs@postgres:5432/upvs
```

---

## 🚀 Жизненный цикл запуска

### 1. docker-compose up -d

```
┌─────────────────────┐
│   postgres          │  Запускается первым
│   (База данных)     │
└──────────┬──────────┘
           │ Ждёт готовности (health check)
           ▼
┌─────────────────────┐
│   init              │  Запускается после postgres
│   (Инициализация)   │
│                     │
│  1. Ждёт postgres   │
│  2. Загружает CSV   │
│  3. Загружает JSONL │
│  4. Завершается     │
└──────────┬──────────┘
           │ Ждёт завершения
           ▼
┌─────────────────────┐
│   api               │  Запускается последним
│   (FastAPI)         │
│                     │
│  - Инициализирует   │
│    DB schema        │
│  - Запускает API    │
│  - Слушает :8000    │
└─────────────────────┘
```

### 2. API готов

```
✅ http://localhost:8000/health
✅ http://localhost:8000/docs
✅ http://localhost:8000/api/tree
```

---

## 📈 Зависимости

### Python (requirements.txt)

```
fastapi==0.111.0          # Web framework
uvicorn==0.30.1           # ASGI server
psycopg2-binary==2.9.9    # PostgreSQL adapter
pydantic==2.8.2           # Data validation
```

**Всего: 4 пакета** (было 8+ в v1.x)

### Docker образы

```
postgres:15               # База данных
python:3.11-slim          # API base image
```

---

## 🗃️ База данных (PostgreSQL)

### Таблицы:

```sql
pages           -- Информация о страницах
text_chunks     -- Текстовые блоки
tables          -- Таблицы с данными
edges           -- Связи между страницами
```

### Индексы:

```sql
idx_pages_url
idx_chunks_page_id
idx_tables_page_id
idx_edges_from_url
idx_edges_to_url
```

---

## 🔌 API эндпоинты

### Навигация:
- `GET /api/tree` - Полное дерево
- `GET /api/tree/search` - Поиск страниц

### Контент:
- `GET /api/page/{page_id}` - Страница целиком

### Таблицы:
- `GET /api/tables/list` - Все таблицы
- `GET /api/tables/search` - Поиск таблиц
- `GET /api/table/{table_id}` - Конкретная таблица
- `GET /api/page/{page_id}/tables` - Таблицы страницы

### Система:
- `GET /health` - Health check
- `GET /docs` - Swagger UI
- `GET /openapi.json` - OpenAPI schema

---

## 📊 Размеры и статистика

### Код:

- **API**: ~400 строк Python
- **Config**: ~15 строк
- **DB**: ~100 строк
- **Scripts**: ~150 строк
- **Всего**: ~650 строк кода

### Документация:

- **9 файлов**: ~2000+ строк markdown
- **Примеры**: 30+ code snippets
- **Команды**: 50+ bash examples

### Данные (примерно):

- **Pages**: ~1000-5000 страниц
- **Text chunks**: ~10000-50000 блоков
- **Tables**: ~500-2000 таблиц
- **Size**: ~50-200 MB сырых данных

---

## 🎯 Что важно понимать

### v2.0 фокусируется на:
1. ✅ **Простота** - минимум зависимостей
2. ✅ **REST API** - структурированные данные
3. ✅ **PostgreSQL** - единственное хранилище
4. ✅ **ChatGPT Actions** - интеграция с AI

### v2.0 НЕ включает:
1. ❌ Локальные LLM модели (vLLM)
2. ❌ Векторный поиск (FAISS)
3. ❌ Embeddings (sentence-transformers)
4. ❌ Web фронтенд (Next.js)
5. ❌ Встроенный RAG

### Причина:
**ChatGPT делает это лучше!** Современные LLM эффективнее работают со структурированными данными через API, чем локальные модели с RAG.

---

## 📚 Дальнейшие шаги

1. 📖 Читайте [START_HERE.md](./START_HERE.md)
2. ⚡ Запускайте: [QUICKSTART.md](./QUICKSTART.md)
3. 🤖 Настраивайте ChatGPT: [CHATGPT_SETUP.md](./CHATGPT_SETUP.md)
4. 🚀 Деплойте: [PRODUCTION.md](./PRODUCTION.md)

---

**Удачи!** 🎉

