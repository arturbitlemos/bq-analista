import json
from pathlib import Path

from mcp_core.library import LibraryEntry, prepend_entry


def test_creates_library_json_if_missing(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    entry = LibraryEntry(
        id="abc", title="T", brand="FARM", date="2026-04-18",
        link="/analyses/x@y.com/abc.html", description="d", tags=["ytd"],
        filename="abc.html", author_email="x@y.com",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert saved[0]["id"] == "abc"
    assert saved[0]["link"].startswith("/analyses/")


def test_prepends_to_existing_list(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    lib.write_text(json.dumps([{"id": "old"}]))
    entry = LibraryEntry(
        id="new", title="T", brand="B", date="2026-04-18",
        link="/x", description="d", tags=[], filename="new.html",
        author_email="x@y.com",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert [s["id"] for s in saved] == ["new", "old"]


def test_author_email_is_persisted(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    entry = LibraryEntry(
        id="abc", title="T", brand="FARM", date="2026-04-23",
        link="/analyses/vendas-linx/public/abc.html",
        description="d", tags=[], filename="abc.html",
        author_email="artur.lemos@somagrupo.com.br",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert saved[0]["author_email"] == "artur.lemos@somagrupo.com.br"
