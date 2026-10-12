from types import SimpleNamespace

import pytest

from seirama_mcp import config, documents


class FakeSentenceTransformer:
    def __init__(self, model_name, **kwargs):
        self.model_name = model_name
        self.kwargs = kwargs
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        rows = [texts] if isinstance(texts, str) else texts
        return [[1.0] + [0.0] * 767 for _ in rows]


def test_document_and_query_use_model_card_prompts():
    model = FakeSentenceTransformer("google/embeddinggemma-2")
    factory_kwargs = {}

    def model_factory(model_name, **kwargs):
        factory_kwargs.update(kwargs)
        return model

    embedder = documents.EmbeddingGemma(model_factory=model_factory)

    vectors = embedder.embed_documents(["teks"])
    query_vector = embedder.embed_query("pertanyaan")

    assert len(vectors[0]) == 768
    assert len(query_vector) == 768
    assert [kwargs["prompt_name"] for _, kwargs in model.calls] == ["Document", "SearchQuery"]
    assert all(kwargs["normalize_embeddings"] for _, kwargs in model.calls)
    assert all(kwargs["precision"] == "float32" for _, kwargs in model.calls)
    assert model.calls[0][1]["batch_size"] == 4
    assert model.calls[0][1]["show_progress_bar"] is False
    assert model.calls[1][1]["show_progress_bar"] is False
    assert factory_kwargs["config_kwargs"] == {"vision_config": None, "audio_config": None}


def test_document_batch_enables_progress_when_split():
    model = FakeSentenceTransformer("google/embeddinggemma-2")
    embedder = documents.EmbeddingGemma(model_factory=lambda *args, **kwargs: model)

    embedder.embed_documents(["teks"] * 5)

    assert model.calls[0][1]["batch_size"] == 4
    assert model.calls[0][1]["show_progress_bar"] is True


def test_embedding_batch_size_can_be_configured(monkeypatch):
    monkeypatch.setenv("MODEL_EMBEDDING_BATCH_SIZE", "2")

    settings = config.Settings()

    assert settings.model_embedding_batch_size == 2


def test_default_model_and_collection(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)

    settings = config.Settings()

    assert settings.embedding_model == "google/embeddinggemma-2"
    assert settings.model_embedding_batch_size == 4
    assert settings.qdrant_collection == "seirama_documents_embeddinggemma2"


def test_new_collection_uses_embedding_dimension():
    calls = []
    fake_client = SimpleNamespace(
        collection_exists=lambda name: False,
        create_collection=lambda **kwargs: calls.append(kwargs),
    )

    documents.ensure_document_collection(fake_client, "new-collection")

    assert calls[0]["collection_name"] == "new-collection"
    assert calls[0]["vectors_config"].size == 768


def test_incompatible_collection_is_not_deleted_or_recreated():
    fake_client = SimpleNamespace(
        collection_exists=lambda name: True,
        get_collection=lambda name: SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=384)))
        ),
        delete_collection=lambda **kwargs: pytest.fail("must not delete collection"),
        create_collection=lambda **kwargs: pytest.fail("must not recreate collection"),
    )

    with pytest.raises(RuntimeError, match="768|QDRANT_COLLECTION"):
        documents.ensure_document_collection(fake_client, "old-collection")


def test_wrong_embedding_dimension_is_rejected():
    model = FakeSentenceTransformer("google/embeddinggemma-2")
    model.encode = lambda texts, **kwargs: [[0.5, 0.5]]
    embedder = documents.EmbeddingGemma(model_factory=lambda *args, **kwargs: model)

    with pytest.raises(RuntimeError, match="768"):
        embedder.embed_documents(["teks"])
