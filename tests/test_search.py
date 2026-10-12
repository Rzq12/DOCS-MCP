from types import SimpleNamespace

import pytest

from seirama_mcp import config, documents


class SearchEmbedder:
    def embed_query(self, query):
        return [1.0] + [0.0] * 767


class SearchClient:
    def query_points(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(points=[])


@pytest.fixture
def search_fixture(monkeypatch):
    client = SearchClient()
    settings = SimpleNamespace(qdrant_collection="test", search_score_threshold=None)
    monkeypatch.setattr(documents, "settings", settings)
    monkeypatch.setattr(documents, "qdrant", lambda: (client, SearchEmbedder()))
    return SimpleNamespace(client=client, settings=settings,
                           run_search=lambda query: documents.search(query, None, 5))


def test_search_omits_unset_threshold(search_fixture):
    search_fixture.run_search("pertanyaan")

    assert "score_threshold" not in search_fixture.client.kwargs
    assert search_fixture.client.kwargs["query_filter"].must[0].key == "indexed"


def test_search_uses_configured_threshold(search_fixture):
    search_fixture.settings.search_score_threshold = 0.42

    search_fixture.run_search("pertanyaan")

    assert search_fixture.client.kwargs["score_threshold"] == 0.42


def test_invalid_threshold_fails_with_environment_name(monkeypatch):
    monkeypatch.setenv("SEARCH_SCORE_THRESHOLD", "invalid")

    with pytest.raises(ValueError, match="SEARCH_SCORE_THRESHOLD"):
        config.Settings()


def test_threshold_outside_valid_range_is_rejected(monkeypatch):
    monkeypatch.setenv("SEARCH_SCORE_THRESHOLD", "1.5")

    with pytest.raises(ValueError, match="SEARCH_SCORE_THRESHOLD"):
        config.Settings()


def test_invalid_embedding_batch_size_is_rejected(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "0")

    with pytest.raises(ValueError, match="EMBEDDING_BATCH_SIZE"):
        config.Settings()
