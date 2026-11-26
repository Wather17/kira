import json
import zipfile

from PIL import Image

from kira.visual_audit import AuditError, _compare, audit_epub
from test_canvas import _write_fixture_epub


def test_audit_reads_spine_and_writes_page_evidence(tmp_path):
    epub = tmp_path / "book.epub"
    _write_fixture_epub(epub)
    source = tmp_path / "pages"
    source.mkdir()
    Image.new("RGB", (100, 150), "white").save(source / "page-01.jpg")

    report = audit_epub(epub, tmp_path / "audit", source_path=source, render=False)

    assert report["page_count"] == 2
    assert report["pages"][1]["epub_image"] == "OEBPS/Images/page.jpg"
    assert report["pages"][1]["status"] in {"pass", "suspect"}
    assert report["preview"]["status"] == "not_requested"
    saved = json.loads((tmp_path / "audit/report.json").read_text())
    assert saved["epub_sha256"] == report["epub_sha256"]


def test_audit_rejects_epub_without_spine_images(tmp_path):
    epub = tmp_path / "empty.epub"
    with zipfile.ZipFile(epub, "w") as archive:
        archive.writestr("META-INF/container.xml", "<container/>")
    try:
        audit_epub(epub, tmp_path / "audit", render=False)
    except AuditError as exc:
        assert "container has no package" in str(exc)
    else:
        raise AssertionError("invalid EPUB must not be reported as audited")


def test_comparison_flags_edge_crop_but_allows_resize():
    source = Image.new("RGB", (300, 450), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(source)
    draw.rectangle((5, 5, 294, 444), outline="black", width=5)
    draw.rectangle((80, 100, 220, 350), fill="black")

    cropped = source.crop((30, 0, 300, 450)).resize((300, 450))
    _, crop_findings = _compare(source, cropped)
    assert "edge_content_may_be_clipped" in crop_findings

    resized = source.resize((150, 225)).resize((300, 450))
    _, resize_findings = _compare(source, resized)
    assert "edge_content_may_be_clipped" not in resize_findings
