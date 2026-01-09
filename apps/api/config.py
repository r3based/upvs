from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_key: str


def get_settings() -> Settings:
    api_key = os.getenv("API_KEY", "your-secret-api-key-here")
    
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql://upvs:upvs@postgres:5432/upvs"),
        api_key=api_key,
    )
