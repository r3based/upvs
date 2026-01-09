#!/usr/bin/env python3
"""
Скрипт для экспорта OpenAPI schema в файл.

Использование:
    python scripts/export_openapi.py

Результат:
    Создаст файл openapi.json в корне проекта
"""

import json
import sys
from pathlib import Path

# Добавляем путь к apps в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Временно включаем OpenAPI для экспорта
import os
os.environ["ENABLE_OPENAPI_EXPORT"] = "true"

from apps.api.main import app


def export_openapi():
    """Экспортирует OpenAPI schema в файл"""
    
    # Получаем schema
    openapi_schema = app.openapi()
    
    # Путь к файлу
    output_path = Path(__file__).parent.parent / "openapi.json"
    
    # Записываем в файл
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, ensure_ascii=False, indent=2)
    
    print(f"✅ OpenAPI schema экспортирован в: {output_path}")
    print(f"📊 Размер файла: {output_path.stat().st_size} bytes")
    
    # Выводим статистику
    paths_count = len(openapi_schema.get("paths", {}))
    print(f"🔌 Количество эндпоинтов: {paths_count}")
    
    return output_path


if __name__ == "__main__":
    try:
        export_openapi()
    except Exception as e:
        print(f"❌ Ошибка при экспорте OpenAPI: {e}", file=sys.stderr)
        sys.exit(1)

