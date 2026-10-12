def _cell_text(cell, document):
    get_text = getattr(cell, "_get_text", None)
    if callable(get_text):
        try:
            return str(get_text(doc=document) or "").strip()
        except Exception:
            try:
                return str(get_text() or "").strip()
            except Exception:
                return str(getattr(cell, "text", "") or "").strip()
    return str(getattr(cell, "text", "") or "").strip()


def _table_text(item, document):
    export = getattr(item, "export_to_markdown", None)
    if callable(export):
        try:
            text = export(document)
        except Exception:
            try:
                text = export()
            except Exception:
                text = ""
        text = str(text or "").strip()
        if text:
            return text

    grid = getattr(getattr(item, "data", None), "grid", None)
    if grid:
        rows = [" | ".join(_cell_text(cell, document) for cell in row) for row in grid]
        return "\n".join(row for row in rows if row.strip(" |"))

    return str(getattr(item, "text", "") or "").strip()


def docling_page_text(document, items):
    page_text = {}
    for item, _ in items:
        table_data = getattr(item, "data", None)
        is_table = item.__class__.__name__ == "TableItem" or hasattr(table_data, "grid")
        if is_table:
            text = _table_text(item, document)
        else:
            text = str(getattr(item, "text", "") or "").strip()

        if not text:
            continue

        for provenance in getattr(item, "prov", []) or []:
            page_number = getattr(provenance, "page_no", None)
            if page_number is not None:
                page_text.setdefault(page_number, []).append(text)

    return [(number, "\n\n".join(parts)) for number, parts in sorted(page_text.items())]
