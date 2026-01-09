#!/usr/bin/env python3
"""
Скрипт для предзагрузки модели sentence-transformers на хосте.
Запустите этот скрипт на хосте перед запуском docker-compose,
чтобы модель была загружена в кэш.
"""

from __future__ import annotations

import os
import sys

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Установите sentence-transformers: pip install sentence-transformers")
    sys.exit(1)


def main() -> None:
    model_name = os.getenv(
        "EMBEDDINGS_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    
    print(f"Загрузка модели: {model_name}")
    print("Это может занять несколько минут при первом запуске...")
    
    try:
        model = SentenceTransformer(model_name)
        print(f"✅ Модель успешно загружена: {model_name}")
        print(f"Кэш находится в: {os.path.expanduser('~/.cache/huggingface/')}")
    except Exception as exc:
        print(f"❌ Ошибка загрузки модели: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

