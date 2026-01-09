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

Все шаги выполняются автоматически при запуске docker-compose!

1. Убедитесь, что файлы лежат в `data/raw`:

```
pages.csv
text_chunks.jsonl
tables.jsonl
edges.csv
```

2. (Опционально) Предзагрузите модель на хосте для ускорения:

```bash
pip install sentence-transformers
python scripts/preload_model.py
```

3. Запустите все сервисы:

**Без vLLM (только поиск и навигация):**
```bash
docker compose -f docker/docker-compose.yml up --build
```

**С vLLM (полный RAG с генерацией ответов, требует GPU):**
```bash
docker compose -f docker/docker-compose.yml --profile vllm up --build
```

Скрипт инициализации автоматически:
- Дождется готовности PostgreSQL
- Соберет фронт-бандлы
- Загрузит данные в Postgres
- Соберет FAISS индекс (требуется интернет или предзагруженная модель)

4. Проверьте smoke-тесты:

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

## Запуск vLLM для вопрос-ответа

Для использования функции вопрос-ответ (RAG) с генерацией ответов требуется vLLM и GPU.

### Настройка GPU для Docker

**Перед запуском vLLM убедитесь, что GPU доступен в Docker:**

1. Установите NVIDIA Container Toolkit (если еще не установлен):

**Ubuntu/Debian:**
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

**Arch Linux:**
```bash
# Обновите базу данных пакетов
sudo pacman -Sy

# Попробуйте установить
sudo pacman -S nvidia-container-toolkit

# Если пакет недоступен на зеркалах, попробуйте из AUR:
# yay -S nvidia-container-toolkit
# или
# paru -S nvidia-container-toolkit

# После установки настройте Docker для использования nvidia runtime:
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

2. Проверьте, что GPU виден в Docker:
```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

Если команда выше работает, GPU настроен правильно.

### Запуск vLLM

**Вариант 1: Запустить все сервисы сразу (включая vLLM)**
```bash
docker compose -f docker/docker-compose.yml --profile vllm up --build
```

**Вариант 2: Запустить vLLM отдельно после основных сервисов**
```bash
# Сначала основные сервисы
docker compose -f docker/docker-compose.yml up --build

# Затем vLLM в другом терминале
docker compose -f docker/docker-compose.yml --profile vllm up -d vllm
```

**Важно**: 
- vLLM требует GPU и значительный объем памяти (рекомендуется минимум 8GB VRAM)
- Если GPU нет или vLLM не запускается, система все равно работает:
  - ✅ Навигация по статьям
  - ✅ Поиск по содержимому
  - ⚠️ Вопрос-ответ: возвращает найденные источники без генерации ответа

## Troubleshooting

- **FAISS не найден**: убедитесь, что выполнен `build_faiss.py`, а пути в `.env` совпадают.
- **Ошибка загрузки модели из Hugging Face**: 
  - Убедитесь, что контейнер имеет доступ в интернет
  - Или предзагрузите модель на хосте: `python scripts/preload_model.py`
  - Кэш модели будет использован из volume `huggingface_cache`
- **vLLM недоступен или не видит GPU**: 
  - Убедитесь, что установлен `nvidia-container-toolkit` (см. раздел "Запуск vLLM")
  - Проверьте доступность GPU: `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi`
  - Проверьте драйверы NVIDIA: `nvidia-smi` (должен работать на хосте)
  - **Ошибка "driver/library version mismatch"**: 
    - Это означает, что драйвер NVIDIA был обновлен, но система не перезагружена
    - **Решение**: Перезагрузите систему: `sudo reboot`
    - После перезагрузки проверьте снова: `nvidia-smi` и `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi`
  - Запустите vLLM: `docker compose -f docker/docker-compose.yml --profile vllm up -d vllm`
  - Или используйте внешний OpenAI-compatible API, указав `VLLM_URL` в `.env`
  - Без vLLM система вернет найденные источники без генерации ответа
- **Проблемы с DNS**: docker-compose настроен на использование Google DNS (8.8.8.8, 8.8.4.4)
- **Большие файлы**: используйте батчи (по умолчанию 10k для Postgres, 32 для эмбеддингов).
- **Colab экспорт**: проверьте кодировки и отсутствие BOM; JSONL должен быть построчно корректным JSON.
