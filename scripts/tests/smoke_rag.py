from __future__ import annotations

import os
import requests


def main() -> None:
    api_base = os.getenv("API_BASE", "http://localhost:8000")

    print("Проверка /health...")
    health = requests.get(f"{api_base}/health", timeout=10)
    health.raise_for_status()
    print(health.json())

    query = "Что такое метод конечных элементов?"

    print("Проверка /search...")
    search = requests.post(
        f"{api_base}/search",
        json={"query": query, "top_k": 5},
        timeout=30,
    )
    search.raise_for_status()
    search_payload = search.json()
    print("Найдено:", len(search_payload.get("hits", [])))

    print("Проверка /rag...")
    rag = requests.post(
        f"{api_base}/rag",
        json={"query": query, "top_k": 5},
        timeout=120,
    )
    rag.raise_for_status()
    rag_payload = rag.json()
    print("Ответ:\n", rag_payload.get("answer"))
    print("Источники:")
    for source in rag_payload.get("sources", [])[:3]:
        print("-", source.get("title") or source.get("url"))


if __name__ == "__main__":
    main()
