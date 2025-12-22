from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List

import faiss
import numpy as np

from .config import Settings
from .embeddings import EmbeddingProvider, get_provider


@dataclass
class FaissHit:
    chunk_id: str
    page_id: str
    url: str
    score: float
    section_path: List[str]
    source_order: int
    text_preview: str


class FaissStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index: faiss.Index | None = None
        self._id_map: List[Dict[str, object]] | None = None
        self._provider: EmbeddingProvider | None = None

    def _load_index(self) -> None:
        if self._index is not None:
            return
        if not os.path.exists(self._settings.faiss_index_path):
            raise FileNotFoundError(
                f"FAISS индекс не найден: {self._settings.faiss_index_path}"
            )
        if not os.path.exists(self._settings.faiss_map_path):
            raise FileNotFoundError(
                f"FAISS mapping не найден: {self._settings.faiss_map_path}"
            )
        self._index = faiss.read_index(self._settings.faiss_index_path)
        self._id_map = []
        with open(self._settings.faiss_map_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    self._id_map.append(json.loads(line))

    def _get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            self._provider = get_provider(
                self._settings.embeddings_provider,
                self._settings.embeddings_model,
                self._settings.vllm_url,
            )
        return self._provider

    def search(self, query: str, top_k: int) -> List[FaissHit]:
        self._load_index()
        assert self._index is not None
        assert self._id_map is not None
        provider = self._get_provider()
        embeddings = provider.embed([query])
        scores, indices = self._index.search(embeddings, top_k)
        hits: List[FaissHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._id_map):
                continue
            record = self._id_map[idx]
            hits.append(
                FaissHit(
                    chunk_id=str(record["chunk_id"]),
                    page_id=str(record["page_id"]),
                    url=str(record["url"]),
                    score=float(score),
                    section_path=record.get("section_path", []),
                    source_order=int(record.get("source_order", 0)),
                    text_preview=str(record.get("text_preview", "")),
                )
            )
        return hits
