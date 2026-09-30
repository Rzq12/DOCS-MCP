import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    docs_root: Path = PROJECT_ROOT / "Docs"
    codegraph_db: Path = PROJECT_ROOT / ".codegraph.sqlite"
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "seirama_documents")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    document_parser: str = os.getenv("DOCUMENT_PARSER", "docling").lower()
    document_ocr: bool = os.getenv("DOCUMENT_OCR", "true").lower() in {"1", "true", "yes", "on"}
    document_chunk_size: int = 1800
    document_chunk_overlap: int = 250

settings = Settings()
