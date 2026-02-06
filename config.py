from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    llm_model: str = os.getenv("LOCALBRAIN_LLM_MODEL", "llama3.1")
    embedding_model: str = os.getenv("LOCALBRAIN_EMBED_MODEL", "nomic-embed-text")
    chunk_size: int = int(os.getenv("LOCALBRAIN_CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("LOCALBRAIN_CHUNK_OVERLAP", "120"))
    retrieval_k: int = int(os.getenv("LOCALBRAIN_RETRIEVAL_K", "4"))
    collection_name: str = os.getenv("LOCALBRAIN_COLLECTION", "localbrain")

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def chroma_persist_dir(self) -> Path:
        return self.base_dir / ".localbrain" / "chroma"


SETTINGS = Settings()
