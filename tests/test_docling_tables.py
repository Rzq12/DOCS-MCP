from types import SimpleNamespace

from seirama_mcp.docling_tables import docling_page_text


def test_table_uses_markdown_export_on_its_page():
    class TableItem:
        text = ""
        prov = [SimpleNamespace(page_no=2)]

        def export_to_markdown(self, document):
            return "| Unit | Kompetensi |\n| --- | --- |\n| 1 | Analisis kebijakan |"

    result = docling_page_text(object(), [(TableItem(), None)])

    assert result == [(2, "| Unit | Kompetensi |\n| --- | --- |\n| 1 | Analisis kebijakan |")]


def test_table_falls_back_to_cell_grid():
    class TableItem:
        prov = [SimpleNamespace(page_no=1)]
        data = SimpleNamespace(grid=[[SimpleNamespace(text="Unit"), SimpleNamespace(text="Kompetensi")],
                                     [SimpleNamespace(text="1"), SimpleNamespace(text="Analisis")]])

        def export_to_markdown(self, document):
            return ""

    assert docling_page_text(object(), [(TableItem(), None)]) == [(1, "Unit | Kompetensi\n1 | Analisis")]


def test_text_items_and_tables_keep_page_order():
    class TableItem:
        prov = [SimpleNamespace(page_no=1)]
        data = SimpleNamespace(grid=[[SimpleNamespace(text="Hasil")]])

        def export_to_markdown(self, document):
            return "| Hasil |"

    text_item = SimpleNamespace(text="Ringkasan", prov=[SimpleNamespace(page_no=1)])

    assert docling_page_text(object(), [(text_item, None), (TableItem(), None)]) == [
        (1, "Ringkasan\n\n| Hasil |")
    ]
