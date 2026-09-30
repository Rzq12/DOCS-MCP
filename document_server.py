import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from mcp.server.fastmcp import FastMCP
from seirama_mcp import documents

mcp = FastMCP("seirama-documents", host="0.0.0.0", port=8001)

@mcp.tool()
def document_search(query: str, category: str | None = None, limit: int = 10) -> dict:
    """Mencari isi PDF di folder Docs."""
    if not query.strip() or not 1 <= limit <= 50:
        raise ValueError("query wajib diisi dan limit harus antara 1 dan 50")
    documents.index()
    results = documents.search(query, category, limit)
    return {"query": query, "category": category, "count": len(results), "results": results}

@mcp.tool()
def document_get(path: str, page_number: int | None = None) -> dict:
    """Mengambil isi halaman PDF."""
    documents.index()
    return documents.get(path.strip(), page_number)

@mcp.tool()
def document_index(refresh: bool = False) -> dict:
    """Membangun atau memperbarui indeks dokumen."""
    return documents.index(refresh)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")