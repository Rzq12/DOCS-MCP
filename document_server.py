import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from mcp.server.fastmcp import FastMCP
from seirama_mcp import documents

mcp = FastMCP("seirama-documents", host="0.0.0.0", port=8001)

@mcp.tool()
def document_search(query: str, category: str | None = None, limit: int = 5) -> dict:
    """Mencari dokumen berdasarkan makna."""
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("query wajib diisi dan limit harus antara 1 dan 20")
    results = documents.search(query, category.strip() if category else None, limit)
    return {"query": query, "category": category, "count": len(results), "results": results}

@mcp.tool()
def document_get(path: str, page_number: int) -> dict:
    """Mengambil teks satu halaman dokumen."""
    return documents.get(path.strip(), page_number)

@mcp.tool()
def document_index(refresh: bool = False) -> dict:
    """Membangun atau memperbarui indeks dokumen."""
    return documents.index(refresh)

@mcp.tool()
def document_list(category: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    """Mendaftar dokumen atau menghitung dokumen per kategori."""
    if limit < 1 or offset < 0:
        raise ValueError("limit harus positif dan offset tidak boleh negatif")
    return documents.list_documents(category.strip() if category else None, limit, offset)

@mcp.tool()
def document_text_search(query: str, category: str | None = None, limit: int = 5) -> dict:
    """Mencari kata literal dalam teks dokumen."""
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("query wajib diisi dan limit harus antara 1 dan 20")
    results = documents.text_search(query, category.strip() if category else None, limit)
    return {"query": query, "category": category, "count": len(results), "results": results}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")