from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_raw_dir: str
    data_derived_dir: str
    faiss_index_path: str
    faiss_map_path: str
    embeddings_provider: str
    embeddings_model: str
    vllm_url: str
    vllm_model: str
    vllm_api_key: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://upvs:upvs@postgres:5432/upvs"),
        data_raw_dir=os.getenv("DATA_RAW_DIR", "/app/data/raw"),
        data_derived_dir=os.getenv("DATA_DERIVED_DIR", "/app/data/derived"),
        faiss_index_path=os.getenv("FAISS_INDEX_PATH", "/app/data/derived/faiss/index.faiss"),
        faiss_map_path=os.getenv("FAISS_MAP_PATH", "/app/data/derived/faiss/id_map.jsonl"),
        embeddings_provider=os.getenv("EMBEDDINGS_PROVIDER", "st"),
        embeddings_model=os.getenv(
            "EMBEDDINGS_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        vllm_url=os.getenv("VLLM_URL", "http://vllm:8000/v1"),
        vllm_model=os.getenv("VLLM_MODEL", "Qwen/Qwen2-1.5B-Instruct"),
        vllm_api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
    )
