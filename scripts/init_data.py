#!/usr/bin/env python3
"""
Скрипт инициализации данных для UPVS.
Выполняет все необходимые шаги подготовки данных.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def wait_for_postgres(database_url: str, max_retries: int = 30) -> None:
    """Ожидает готовности PostgreSQL"""
    import psycopg2

    print("Ожидание готовности PostgreSQL...")
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(database_url)
            conn.close()
            print("PostgreSQL готов")
            return
        except psycopg2.OperationalError:
            if i < max_retries - 1:
                print(f"Попытка {i + 1}/{max_retries}...")
                time.sleep(2)
            else:
                raise


def run_script(script_path: Path, description: str, args: list[str] | None = None, env: dict | None = None) -> None:
    """Запускает Python скрипт"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    result = subprocess.run(
        cmd,
        env=env_vars,
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Скрипт {script_path} завершился с ошибкой: {result.returncode}")


def main() -> None:
    """Основная функция инициализации"""
    print("=" * 60)
    print("Инициализация данных UPVS")
    print("=" * 60)

    # Получаем переменные окружения
    data_dir = Path(os.getenv("DATA_RAW_DIR", "data/raw"))
    derived_dir = Path(os.getenv("DATA_DERIVED_DIR", "data/derived"))
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://upvs:upvs@postgres:5432/upvs"
    )
    
    # Проверяем наличие исходных данных
    required_files = [
        data_dir / "pages.csv",
        data_dir / "text_chunks.jsonl",
        data_dir / "tables.jsonl",
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    if missing_files:
        print(f"Предупреждение: отсутствуют файлы: {[str(f) for f in missing_files]}")
        print("Продолжаем с доступными файлами...")

    # Шаг 1: Ожидание PostgreSQL
    wait_for_postgres(database_url)

    # Шаг 2: Подготовка фронт-бандлов
    build_bundles_script = Path(__file__).parent.parent / "scripts" / "prepare_front_data" / "build_page_bundles.py"
    if build_bundles_script.exists():
        run_script(
            build_bundles_script,
            "Сборка фронт-бандлов",
            env={"DATA_RAW_DIR": str(data_dir), "DATA_DERIVED_DIR": str(derived_dir)},
        )
    else:
        print("Пропуск: скрипт build_page_bundles.py не найден")

    # Шаг 3: Загрузка данных в Postgres
    load_postgres_script = Path(__file__).parent.parent / "scripts" / "load_postgres" / "load_all.py"
    if load_postgres_script.exists():
        run_script(
            load_postgres_script,
            "Загрузка данных в Postgres",
            args=["--truncate", "--data-dir", str(data_dir)],
            env={"DATABASE_URL": database_url},
        )
    else:
        print("Пропуск: скрипт load_all.py не найден")

    # Шаг 4: Сборка FAISS индекса
    build_faiss_script = Path(__file__).parent.parent / "scripts" / "build_faiss" / "build_faiss.py"
    if build_faiss_script.exists():
        run_script(
            build_faiss_script,
            "Сборка FAISS индекса",
            args=["--data-dir", str(data_dir), "--output-dir", str(derived_dir / "faiss"), "--batch-size", "32"],
            env={
                "EMBEDDINGS_PROVIDER": os.getenv("EMBEDDINGS_PROVIDER", "st"),
                "EMBEDDINGS_MODEL": os.getenv(
                    "EMBEDDINGS_MODEL",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                ),
            },
        )
    else:
        print("Пропуск: скрипт build_faiss.py не найден")

    print("\n" + "=" * 60)
    print("Инициализация завершена успешно!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nОшибка инициализации: {exc}", file=sys.stderr)
        sys.exit(1)

