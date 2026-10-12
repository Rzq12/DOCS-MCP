from types import SimpleNamespace

from seirama_mcp import documents


def test_chunks_prefer_sentence_and_line_boundaries(monkeypatch):
    monkeypatch.setattr(documents, "settings", SimpleNamespace(document_chunk_size=45, document_chunk_overlap=8))
    text = "Kalimat pertama cukup panjang. Kalimat kedua tetap utuh.\n\nParagraf baru dimulai."

    result = documents.chunks(text)

    assert all(len(part) <= 45 for part in result)
    assert any("Kalimat pertama cukup panjang." in part for part in result)
    assert any("Paragraf baru dimulai." in part for part in result)
    assert all(result[index][-8:] == result[index + 1][:8] for index in range(len(result) - 1))


def test_oversized_sentence_preserves_text_with_overlap(monkeypatch):
    monkeypatch.setattr(documents, "settings", SimpleNamespace(document_chunk_size=12, document_chunk_overlap=3))
    text = "satu dua tiga empat lima enam tujuh"

    result = documents.chunks(text)

    assert all(len(part) <= 12 for part in result)
    assert result[0] + "".join(part[3:] for part in result[1:]) == text
    assert all(result[index][-3:] == result[index + 1][:3] for index in range(len(result) - 1))


def test_oversized_unbroken_text_makes_progress(monkeypatch):
    monkeypatch.setattr(documents, "settings", SimpleNamespace(document_chunk_size=5, document_chunk_overlap=2))

    result = documents.chunks("abcdefghijkl")

    assert all(len(part) <= 5 for part in result)
    assert result[0] + "".join(part[2:] for part in result[1:]) == "abcdefghijkl"
