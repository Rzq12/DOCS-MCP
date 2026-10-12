import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} harus berupa bilangan bulat positif") from error
    if parsed <= 0:
        raise ValueError(f"{name} harus berupa bilangan bulat positif")
    return parsed


def _optional_threshold() -> float | None:
    value = os.getenv("SEARCH_SCORE_THRESHOLD")
    if value is None or not value.strip():
        return None
    try:
        threshold = float(value)
    except ValueError as error:
        raise ValueError("SEARCH_SCORE_THRESHOLD harus berupa angka antara 0 dan 1") from error
    if not 0 <= threshold <= 1:
        raise ValueError("SEARCH_SCORE_THRESHOLD harus berupa angka antara 0 dan 1")
    return threshold


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    docs_root: Path = field(default_factory=lambda: Path(os.getenv("DOCS_ROOT", str(PROJECT_ROOT / "Docs"))))
    codegraph_db: Path = field(default_factory=lambda: Path(os.getenv("CODEGRAPH_DB", str(PROJECT_ROOT / ".codegraph.sqlite"))))
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333"))
    qdrant_collection: str = field(default_factory=lambda: os.getenv("QDRANT_COLLECTION", "seirama_documents_embeddinggemma2"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-2"))
    document_parser: str = field(default_factory=lambda: os.getenv("DOCUMENT_PARSER", "docling").lower())
    document_ocr: bool = field(default_factory=lambda: os.getenv("DOCUMENT_OCR", "true").lower() in {"1", "true", "yes", "on"})
    document_ocr_languages: tuple[str, ...] = field(default_factory=lambda: tuple(
        filter(None, os.getenv("DOCUMENT_OCR_LANGUAGES", "iso:id,iso:en").split(","))
    ))
    document_chunk_size: int = 1800
    document_chunk_overlap: int = 250
    embedding_batch_size: int = field(default_factory=lambda: _positive_int("EMBEDDING_BATCH_SIZE", 32))
    model_embedding_batch_size: int = field(default_factory=lambda: _positive_int("MODEL_EMBEDDING_BATCH_SIZE", 4))
    search_score_threshold: float | None = field(default_factory=_optional_threshold)


settings = Settings()
