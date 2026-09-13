import json
from pathlib import Path

from app.ingest import discover_transport_documents


SOURCES_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "sources.json"


def test_only_current_enabled_sources_are_curated():
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    active = [s for s in sources if s.get("enabled", True)]
    assert active
    assert all(s.get("current", True) for s in active)


def test_stale_oeirc_social_card_page_is_excluded():
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    urls = {s["url"] for s in sources if s.get("enabled", True)}
    assert "https://oeirc.ru/transportnaya_karta/socialnaya-tk/" not in urls
    assert "https://oeirc.ru/?page=tk/stk.php" in urls


def test_document_discovery_keeps_only_transport_documents():
    html = """
    <html><body>
      <a href='/tk/docs/rules.pdf'>Правила транспортной системы Сбертройка</a>
      <a href='/docs/accounting.pdf'>Бухгалтерская отчетность</a>
      <a href='/tk/docs/change.docx'>Приказ о внесении изменений в правила ТКП</a>
    </body></html>
    """.encode("utf-8")
    parent = {
        "id": "oeirc-documents-index",
        "url": "https://oeirc.ru/?page=about/docs",
        "kind": "html",
        "authority": "АО ОЕИРЦ",
        "priority": 75,
    }
    docs = discover_transport_documents(html, "https://oeirc.ru/?page=about/docs", parent)
    urls = {d["url"] for d in docs}
    assert "https://oeirc.ru/tk/docs/rules.pdf" in urls
    assert "https://oeirc.ru/tk/docs/change.docx" in urls
    assert "https://oeirc.ru/docs/accounting.pdf" not in urls
