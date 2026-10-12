import hashlib
from types import SimpleNamespace

import pytest
from qdrant_client.models import FieldCondition, Filter, MatchValue

from seirama_mcp import documents


class FakeClient:
    def __init__(self):
        self.points = {}
        self.upsert_sizes = []
        self.last_query_kwargs = None
        self.fail_upsert_call = None
        self.upsert_call_count = 0

    def scroll(self, collection_name, scroll_filter=None, limit=10, with_payload=True, **kwargs):
        matches = [(point_id, record) for point_id, record in self.points.items()
                   if self._matches(record["payload"], scroll_filter)]
        return ([SimpleNamespace(id=point_id, payload=record["payload"]) for point_id, record in matches[:limit]], None)

    def upsert(self, collection_name, points):
        self.upsert_call_count += 1
        self.upsert_sizes.append(len(points))
        if self.fail_upsert_call == self.upsert_call_count:
            raise RuntimeError("upsert failure")
        for point in points:
            self.points[point.id] = {"vector": point.vector, "payload": dict(point.payload)}

    def set_payload(self, collection_name, payload, points):
        for point_id, record in self.points.items():
            if isinstance(points, Filter):
                if self._matches(record["payload"], points):
                    record["payload"].update(payload)
            elif point_id in points:
                record["payload"].update(payload)

    def delete(self, collection_name, points_selector):
        for point_id, record in list(self.points.items()):
            if isinstance(points_selector, Filter):
                if self._matches(record["payload"], points_selector):
                    del self.points[point_id]
            elif point_id in points_selector:
                del self.points[point_id]

    def query_points(self, **kwargs):
        self.last_query_kwargs = kwargs
        return SimpleNamespace(points=[])

    @staticmethod
    def _matches(payload, selector):
        if selector is None:
            return True
        matches = all(
            payload.get(condition.key) == condition.match.value
            for condition in getattr(selector, "must", []) or []
            if isinstance(condition, FieldCondition) and isinstance(condition.match, MatchValue)
        )
        excludes = any(
            payload.get(condition.key) == condition.match.value
            for condition in getattr(selector, "must_not", []) or []
            if isinstance(condition, FieldCondition) and isinstance(condition.match, MatchValue)
        )
        return matches and not excludes

    def active_checksums(self, path):
        return sorted({record["payload"]["checksum"] for record in self.points.values()
                       if record["payload"].get("path") == path and record["payload"].get("indexed") is True})


class FakeEmbedder:
    def __init__(self):
        self.batch_sizes = []
        self.calls = 0
        self.raise_on_call = None

    def embed_documents(self, texts):
        self.calls += 1
        self.batch_sizes.append(len(texts))
        if self.raise_on_call == self.calls:
            raise RuntimeError("embedding failure")
        return [[1.0] + [0.0] * 767 for _ in texts]

    def embed_query(self, query):
        return [1.0] + [0.0] * 767


@pytest.fixture
def index_fixture(monkeypatch, tmp_path):
    docs_root = tmp_path / "Docs"
    docs_root.mkdir()
    pdf_path = docs_root / "folder" / "source.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"original pdf contents")
    fake_client = FakeClient()
    fake_embedder = FakeEmbedder()
    settings = SimpleNamespace(
        docs_root=docs_root,
        document_chunk_size=15,
        document_chunk_overlap=2,
        embedding_batch_size=2,
        qdrant_collection="test",
        search_score_threshold=None,
    )
    monkeypatch.setattr(documents, "settings", settings)
    monkeypatch.setattr(documents, "qdrant", lambda: (fake_client, fake_embedder))
    monkeypatch.setattr(documents, "parse_pdf", lambda path: [(1, "kalimat pertama cukup panjang. kalimat kedua untuk chunk berikutnya.")])
    fixture = SimpleNamespace(client=fake_client, embedder=fake_embedder, settings=settings,
                              path="Docs/folder/source.pdf", pdf_path=pdf_path)

    def change_pdf_content():
        pdf_path.write_bytes(b"changed pdf contents")
        fixture.new_checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    def seed(checksum):
        point_id = int(hashlib.sha256(f"{fixture.path}:{checksum}:seed:1:0".encode()).hexdigest()[:15], 16)
        fake_client.points[point_id] = {
            "vector": [1.0] + [0.0] * 767,
            "payload": {"path": fixture.path, "checksum": checksum, "version_id": checksum,
                       "indexed": True, "page_number": 1, "chunk_index": 0, "text": "old text",
                       "filename": "source.pdf", "category": "folder", "page_count": 1},
        }

    change_pdf_content()
    fixture.new_checksum = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    fixture.run_index = lambda: documents.index()
    fixture.change_pdf_content = change_pdf_content
    fixture.seed_indexed_document = seed
    return fixture


def test_index_embeds_and_upserts_at_most_configured_batch_size(index_fixture):
    index_fixture.run_index()

    assert max(index_fixture.embedder.batch_sizes) <= index_fixture.settings.embedding_batch_size
    assert max(index_fixture.client.upsert_sizes) <= index_fixture.settings.embedding_batch_size


def test_embedding_failure_keeps_old_document_searchable(index_fixture):
    index_fixture.seed_indexed_document("old")
    index_fixture.change_pdf_content()
    index_fixture.embedder.raise_on_call = 2

    with pytest.raises(RuntimeError, match="embedding failure"):
        index_fixture.run_index()

    assert index_fixture.client.active_checksums(index_fixture.path) == ["old"]
    assert any(record["payload"].get("indexed") is False for record in index_fixture.client.points.values())


def test_upsert_failure_keeps_old_document_searchable(index_fixture):
    index_fixture.seed_indexed_document("old")
    index_fixture.change_pdf_content()
    index_fixture.client.fail_upsert_call = 2

    with pytest.raises(RuntimeError, match="upsert failure"):
        index_fixture.run_index()

    assert index_fixture.client.active_checksums(index_fixture.path) == ["old"]


def test_parse_failure_keeps_old_document_searchable(index_fixture, monkeypatch):
    index_fixture.seed_indexed_document("old")
    index_fixture.change_pdf_content()
    monkeypatch.setattr(documents, "parse_pdf", lambda path: (_ for _ in ()).throw(RuntimeError("parse failure")))

    with pytest.raises(RuntimeError, match="parse failure"):
        index_fixture.run_index()

    assert index_fixture.client.active_checksums(index_fixture.path) == ["old"]


def test_empty_parsed_document_does_not_delete_old_version(index_fixture, monkeypatch):
    index_fixture.seed_indexed_document("old")
    index_fixture.change_pdf_content()
    monkeypatch.setattr(documents, "parse_pdf", lambda path: [(1, "   ")])

    with pytest.raises(RuntimeError, match="tidak menghasilkan chunk"):
        index_fixture.run_index()

    assert index_fixture.client.active_checksums(index_fixture.path) == ["old"]


def test_force_reindex_failure_keeps_same_checksum_version(index_fixture):
    index_fixture.seed_indexed_document(index_fixture.new_checksum)
    index_fixture.embedder.raise_on_call = 1

    with pytest.raises(RuntimeError, match="embedding failure"):
        documents.index(force=True)

    assert index_fixture.client.active_checksums(index_fixture.path) == [index_fixture.new_checksum]


def test_success_publishes_new_version_then_removes_old(index_fixture):
    index_fixture.seed_indexed_document("old")

    result = index_fixture.run_index()

    assert result["indexed"] == 1
    assert index_fixture.client.active_checksums(index_fixture.path) == [index_fixture.new_checksum]


def test_retry_cleans_stale_versions_when_checksum_matches(index_fixture):
    index_fixture.seed_indexed_document(index_fixture.new_checksum)
    index_fixture.seed_indexed_document("old")

    result = index_fixture.run_index()

    assert result["skipped"] == 1
    assert index_fixture.client.active_checksums(index_fixture.path) == [index_fixture.new_checksum]


def test_staging_points_are_filtered_from_search_and_get(index_fixture):
    index_fixture.client.points[1] = {"vector": [0.0] * 768, "payload": {
        "path": index_fixture.path, "indexed": False, "page_number": 1,
        "text": "staged", "category": "folder",
    }}

    documents.search("query", None, 5)
    page = documents.get(index_fixture.path, 1)
    listed = documents.list_documents(category_filter="folder")
    literal_results = documents.text_search("staged")

    assert index_fixture.client.last_query_kwargs["query_filter"].must[-1].key == "indexed"
    assert page == {"found": False, "document": None}
    assert listed["documents"] == []
    assert literal_results == []
