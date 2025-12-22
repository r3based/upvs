from abc import ABC, abstractmethod
from typing import List

import numpy as np
import requests
from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    @abstractmethod
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


def get_provider(provider: str, model: str, http_url: str) -> EmbeddingProvider:
    if provider == "http":
        return HttpEmbeddingProvider(http_url)
    return SentenceTransformersEmbeddingProvider(model)
