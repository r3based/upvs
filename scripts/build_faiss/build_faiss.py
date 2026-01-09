from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List

import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer


def read_jsonl(path: Path) -> Generator[dict, None, None]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


@dataclass
class ChunkMeta:
    chunk_id: str
    page_id: str
    url: str
    section_path: List[str]
    source_order: int
    text_preview: str


class EmbeddingProvider:
    def embed(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError


class SentenceTransformersEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(embeddings, dtype="float32")


class HttpEmbeddingProvider(EmbeddingProvider):
    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")

    def embed(self, texts: List[str]) -> np.ndarray:
        response = requests.post(
            f"{self._url}/embeddings",
            json={"input": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        vectors = [item["embedding"] for item in data.get("data", [])]
        return np.asarray(vectors, dtype="float32")


def get_provider(provider: str, model_name: str, http_url: str) -> EmbeddingProvider:
    if provider == "http":
        return HttpEmbeddingProvider(http_url)
    return SentenceTransformersEmbeddingProvider(model_name)


def load_page_info(pages_path: Path) -> Dict[str, Dict[str, str]]:
    """Загружает информацию о страницах: url и title"""
    page_info: Dict[str, Dict[str, str]] = {}
    with pages_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("page_id"):
                page_id = str(row["page_id"])
                page_info[page_id] = {
                    "url": str(row.get("url") or ""),
                    "title": str(row.get("title") or ""),
                }
    return page_info


def load_table_captions(tables_path: Path) -> Dict[str, List[str]]:
    """Загружает названия таблиц по page_id"""
    table_captions: Dict[str, List[str]] = {}
    if not tables_path.exists():
        return table_captions
    
    for item in read_jsonl(tables_path):
        page_id = str(item.get("page_id", ""))
        caption = item.get("caption", "")
        if page_id and caption:
            if page_id not in table_captions:
                table_captions[page_id] = []
            table_captions[page_id].append(str(caption))
    return table_captions


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка FAISS индекса для UPVS")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/derived/faiss")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    provider_name = os.getenv("EMBEDDINGS_PROVIDER", "st")
    model_name = os.getenv(
        "EMBEDDINGS_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    http_url = os.getenv("EMBEDDINGS_HTTP_URL", "http://localhost:8000/v1")

    data_dir = Path(args.data_dir)
    chunks_path = data_dir / "text_chunks.jsonl"
    pages_path = data_dir / "pages.csv"

    if not chunks_path.exists():
        raise FileNotFoundError(chunks_path)
    if not pages_path.exists():
        raise FileNotFoundError(pages_path)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = get_provider(provider_name, model_name, http_url)
    page_info = load_page_info(pages_path)
    
    tables_path = data_dir / "tables.jsonl"
    table_captions = load_table_captions(tables_path)

    embeddings_list: List[np.ndarray] = []
    metas: List[ChunkMeta] = []

    batch_texts: List[str] = []
    batch_meta: List[ChunkMeta] = []

    for item in read_jsonl(chunks_path):
        page_id = str(item["page_id"])
        original_text = item.get("text", "")
        
        # Обогащаем текст контекстом страницы и таблиц
        enriched_parts = []
        
        # Добавляем название страницы
        page_data = page_info.get(page_id, {})
        if page_data.get("title"):
            enriched_parts.append(page_data["title"])
        
        # Добавляем названия таблиц с этой страницы
        if page_id in table_captions:
            enriched_parts.extend(table_captions[page_id])
        
        # Добавляем section_path
        section_path = item.get("section_path") or []
        if section_path:
            enriched_parts.extend(section_path)
        
        # Добавляем оригинальный текст
        enriched_parts.append(original_text)
        
        # Собираем обогащенный текст
        enriched_text = ". ".join(enriched_parts)
        
        batch_texts.append(enriched_text)
        batch_meta.append(
            ChunkMeta(
                chunk_id=str(item["chunk_id"]),
                page_id=page_id,
                url=page_data.get("url", ""),
                section_path=section_path,
                source_order=int(item.get("source_order", 0)),
                text_preview=original_text[:240],
            )
        )
        if len(batch_texts) >= args.batch_size:
            embeddings_list.append(provider.embed(batch_texts))
            metas.extend(batch_meta)
            batch_texts = []
            batch_meta = []

    if batch_texts:
        embeddings_list.append(provider.embed(batch_texts))
        metas.extend(batch_meta)

    embeddings = np.vstack(embeddings_list)
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    faiss.write_index(index, str(output_dir / "index.faiss"))

    with (output_dir / "id_map.jsonl").open("w", encoding="utf-8") as handle:
        for meta in metas:
            record = {
                "chunk_id": meta.chunk_id,
                "page_id": meta.page_id,
                "url": meta.url,
                "section_path": meta.section_path,
                "source_order": meta.source_order,
                "text_preview": meta.text_preview,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    with (output_dir / "meta.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {"dimension": dimension, "provider": provider_name, "model": model_name},
            handle,
            ensure_ascii=False,
        )

    print(f"Готово. Векторов: {embeddings.shape[0]}")


if __name__ == "__main__":
    main()
