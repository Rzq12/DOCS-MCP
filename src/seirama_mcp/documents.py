import hashlib
import logging
import re
import uuid

from .config import settings
from .docling_tables import docling_page_text
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

logger = logging.getLogger(__name__)
EMBEDDING_DIMENSION = 768


class EmbeddingGemma:
    def __init__(self, model_name=None, model_factory=None):
        self.model_name = model_name or settings.embedding_model
        self._model_factory = model_factory
        self._model = None

    def _get_model(self):
        if self._model is None:
            from huggingface_hub import snapshot_download

            logger.info("Memeriksa cache model embedding %s", self.model_name)
            model_path = snapshot_download(
                repo_id=self.model_name,
                tqdm_class=_HfProgressBar,
            )
            logger.info("Berkas model tersedia di %s; memuat encoder teks", model_path)
            model_factory = self._model_factory
            if model_factory is None:
                from sentence_transformers import SentenceTransformer

                model_factory = SentenceTransformer
            self._model = model_factory(
                model_path,
                config_kwargs={"vision_config": None, "audio_config": None},
            )
            logger.info("Model embedding siap")
        return self._model

    def _encode(self, texts, prompt_name):
        vectors = self._get_model().encode(
            texts,
            prompt_name=prompt_name,
            normalize_embeddings=True,
            precision="float32",
            convert_to_numpy=True,
            batch_size=settings.model_embedding_batch_size if prompt_name == "Document" else 1,
            show_progress_bar=prompt_name == "Document" and len(texts) > settings.model_embedding_batch_size,
        )
        result = vectors.tolist() if hasattr(vectors, "tolist") else vectors
        if texts and len(result) != len(texts):
            raise RuntimeError("EmbeddingGemma mengembalikan jumlah vektor yang tidak sesuai")
        if any(len(vector) != EMBEDDING_DIMENSION for vector in result):
            raise RuntimeError(f"EmbeddingGemma harus menghasilkan vektor {EMBEDDING_DIMENSION} dimensi")
        return result

    def embed_documents(self, texts):
        return self._encode(texts, "Document")

    def embed_query(self, query):
        return self._encode([query], "SearchQuery")[0]


try:
    from huggingface_hub.utils import tqdm as _HfProgressBar
except ImportError:
    _HfProgressBar = None


def ensure_document_collection(qdrant_client, collection_name):
    if qdrant_client.collection_exists(collection_name):
        collection = qdrant_client.get_collection(collection_name)
        vectors = collection.config.params.vectors
        if isinstance(vectors, dict):
            dimensions = {value.size for value in vectors.values()}
            compatible = dimensions == {EMBEDDING_DIMENSION}
        else:
            compatible = getattr(vectors, "size", None) == EMBEDDING_DIMENSION
        if not compatible:
            raise RuntimeError(
                f"Koleksi Qdrant '{collection_name}' tidak memiliki vektor {EMBEDDING_DIMENSION} dimensi. "
                "Atur QDRANT_COLLECTION ke nama koleksi baru lalu indeks ulang; koleksi lama tidak dihapus."
            )
        return
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
    )


client = QdrantClient(url=settings.qdrant_url)
embedder = EmbeddingGemma()
ensure_document_collection(client, settings.qdrant_collection)


def category(path):
    try:
        return path.relative_to(settings.docs_root).parts[0]
    except (ValueError, IndexError):
        return "Lainnya"


def chunks(text):
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()
    if not text:
        return []
    size = settings.document_chunk_size
    overlap = settings.document_chunk_overlap
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("document_chunk_overlap tidak valid")

    result = []
    start = 0
    while start < len(text):
        max_end = min(start + size, len(text))
        if max_end == len(text):
            end = max_end
        else:
            window = text[start:max_end]
            paragraph_breaks = [match.end() for match in re.finditer(r"\n\s*\n+", window)]
            line_breaks = [match.end() for match in re.finditer(r"\n+", window)]
            sentence_breaks = [match.end() for match in re.finditer(r"[.!?](?:[ \t]+|\n+)", window)]
            word_breaks = [match.end() for match in re.finditer(r"\s+", window)]
            minimum = max(1, int(size * 0.6))
            preferred = next(
                (breaks for breaks in (paragraph_breaks, line_breaks, sentence_breaks, word_breaks)
                 if any(position >= minimum for position in breaks)),
                [],
            )
            end = start + (preferred[-1] if preferred else len(window))

        result.append(text[start:end])
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return result


def parse_pdf(path):
    if settings.document_parser == "pypdf":
        from pypdf import PdfReader

        return [(number, page.extract_text() or "") for number, page in enumerate(PdfReader(str(path)).pages, 1)]
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as error:
        raise RuntimeError("Parser Docling belum terpasang; gunakan DOCUMENT_PARSER=pypdf") from error
    options = PdfPipelineOptions()
    options.do_ocr = settings.document_ocr
    options.ocr_options.lang = list(settings.document_ocr_languages)
    options.do_table_structure = True
    options.table_structure_options.do_cell_matching = True
    document = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    ).convert(str(path)).document
    return docling_page_text(document, document.iterate_items()) or [(1, document.export_to_markdown())]


def qdrant():
    return client, embedder


def _filter(**conditions):
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(must=[FieldCondition(key=key, match=MatchValue(value=value)) for key, value in conditions.items()])


def _scroll_all(qdrant_client, scroll_filter):
    points = []
    offset = None
    while True:
        batch, offset = qdrant_client.scroll(
            settings.qdrant_collection,
            scroll_filter=scroll_filter,
            limit=1000,
            offset=offset,
            with_payload=True,
        )
        points.extend(batch)
        if offset is None:
            return points


def _delete_stale_versions(qdrant_client, relative, version_id):
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="path", match=MatchValue(value=relative))],
            must_not=[FieldCondition(key="version_id", match=MatchValue(value=version_id))],
        ),
    )


def index(force=False):
    pdfs = sorted(settings.docs_root.rglob("*.pdf")) if settings.docs_root.exists() else []
    if not pdfs:
        return {"indexed": 0, "skipped": 0, "pdf_count": 0}
    qdrant_client, vectorizer = qdrant()
    indexed = skipped = 0
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

    batch_size = settings.embedding_batch_size
    if batch_size <= 0:
        raise ValueError("EMBEDDING_BATCH_SIZE harus positif")

    for path in pdfs:
        relative = str(path.relative_to(settings.docs_root.parent)).replace("\\", "/")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        current_filter = Filter(
            must=[FieldCondition(key="path", match=MatchValue(value=relative)),
                  FieldCondition(key="checksum", match=MatchValue(value=checksum)),
                  FieldCondition(key="indexed", match=MatchValue(value=True))]
        )
        current_points = _scroll_all(qdrant_client, current_filter)
        if current_points and not force:
            skipped += 1
            active_version = (current_points[0].payload or {}).get("version_id")
            if active_version:
                _delete_stale_versions(qdrant_client, relative, active_version)
            continue

        version_id = uuid.uuid4().hex
        version_filter = Filter(
            must=[FieldCondition(key="path", match=MatchValue(value=relative)),
                  FieldCondition(key="version_id", match=MatchValue(value=version_id))]
        )
        logger.info("Memproses PDF %s", relative)
        pages = parse_pdf(path)
        page_count = len(pages)
        pending = []

        def upsert_batch():
            if not pending:
                return
            texts = [item[1] for item in pending]
            vectors = vectorizer.embed_documents(texts)
            if len(vectors) != len(pending):
                raise RuntimeError("Jumlah vektor embedding tidak cocok dengan jumlah chunk")
            records = []
            for (point_id, text, page_number, chunk_index), vector in zip(pending, vectors):
                records.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"text": text, "path": relative, "filename": path.name,
                             "category": category(path), "page_number": page_number,
                             "chunk_index": chunk_index, "checksum": checksum,
                             "version_id": version_id, "page_count": page_count, "indexed": False},
                ))
            qdrant_client.upsert(collection_name=settings.qdrant_collection, points=records)
            pending.clear()

        total_chunks = 0
        for page_number, page_text in pages:
            text = re.sub(r"(?<!\n)-\n(?=\w)", "", page_text or "")
            text = re.sub(r"[ \t]+", " ", text).strip()
            for chunk_index, text_chunk in enumerate(chunks(text)):
                total_chunks += 1
                point_id = int(hashlib.sha256(
                    f"{relative}:{checksum}:{version_id}:{page_number}:{chunk_index}".encode()
                ).hexdigest()[:15], 16)
                pending.append((point_id, text_chunk, page_number, chunk_index))
                if len(pending) >= batch_size:
                    logger.info("Embedding dan menyimpan batch PDF %s (%d chunk selesai)", relative, total_chunks)
                    upsert_batch()
        upsert_batch()

        if not total_chunks or not _scroll_all(qdrant_client, version_filter):
            raise RuntimeError(f"PDF tidak menghasilkan chunk yang dapat diindeks: {relative}")
        qdrant_client.set_payload(
            collection_name=settings.qdrant_collection,
            payload={"indexed": True},
            points=version_filter,
        )
        _delete_stale_versions(qdrant_client, relative, version_id)
        indexed += 1
        logger.info("Selesai mengindeks PDF %s (%d chunk)", relative, total_chunks)

    return {"indexed": indexed, "skipped": skipped, "pdf_count": len(pdfs), "storage": "qdrant"}


def _read_filter(category_filter=None, **conditions):
    conditions["indexed"] = True
    if category_filter:
        conditions["category"] = category_filter
    return _filter(**conditions)


def search(query, category_filter, limit):
    qdrant_client, vectorizer = qdrant()
    kwargs = {
        "collection_name": settings.qdrant_collection,
        "query": vectorizer.embed_query(query),
        "query_filter": _read_filter(category_filter),
        "limit": limit,
        "with_payload": True,
    }
    if settings.search_score_threshold is not None:
        kwargs["score_threshold"] = settings.search_score_threshold
    points = qdrant_client.query_points(**kwargs).points
    return [{"score": point.score, "filename": point.payload.get("filename"),
             "category": point.payload.get("category"), "page_number": point.payload.get("page_number"),
             "text": point.payload.get("text", "")[:500]} for point in points]


def get(path, page_number):
    normalized = path.replace("\\", "/").lstrip("./")
    qdrant_client, _ = qdrant()
    points = _scroll_all(qdrant_client, _filter(path=normalized, page_number=page_number, indexed=True))
    if not points:
        return {"found": False, "document": None}
    payloads = [point.payload or {} for point in points]
    text = "\n\n".join(item.get("text", "") for item in sorted(payloads, key=lambda value: value.get("chunk_index", 0)))
    first = payloads[0]
    return {"found": True, "document": {"filename": first.get("filename"), "page_number": page_number, "text": text}}


def list_documents(category_filter=None, limit=50, offset=0):
    qdrant_client, _ = qdrant()
    points = _scroll_all(qdrant_client, _read_filter(category_filter))
    unique = {item.get("path"): item for item in (point.payload or {} for point in points) if item.get("path")}
    ordered = sorted(unique.values(), key=lambda item: (item.get("category", ""), item.get("filename", "")))
    if not category_filter:
        counts = {}
        for item in ordered:
            category_name = item.get("category", "Lainnya")
            counts[category_name] = counts.get(category_name, 0) + 1
        return {"count": len(counts), "categories": [{"category": key, "count": value} for key, value in sorted(counts.items())]}
    selected = ordered[offset:offset + limit]
    return {"count": len(ordered), "documents": [{"path": item.get("path"), "page_count": item.get("page_count")} for item in selected]}


def text_search(query, category_filter=None, limit=5):
    qdrant_client, _ = qdrant()
    points = _scroll_all(qdrant_client, _read_filter(category_filter))
    terms = [term for term in re.findall(r"[\w-]+", query.lower()) if len(term) > 2]
    results = []
    for point in points:
        payload = point.payload or {}
        text = payload.get("text", "")
        lower = text.lower()
        match = next(((lower.find(term), term) for term in terms if lower.find(term) >= 0), None)
        if match is None:
            continue
        position, term = match
        start = max(0, position - 75)
        end = min(len(text), position + len(term) + 75)
        results.append({"filename": payload.get("filename"), "page_number": payload.get("page_number"), "snippet": text[start:end]})
        if len(results) >= limit:
            break
    return results
