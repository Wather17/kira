from io import BytesIO
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image, ImageOps

from kira.canvas import CanvasConfig, CanvasError, fit_image_to_canvas, normalize_epub


def _jpeg_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _write_fixture_epub(path: Path) -> None:
    container = b'''<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
    opf = b'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Canvas fixture</dc:title></metadata>
  <manifest>
    <item id="cover" href="Images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>
    <item id="cover-page" href="Text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="page" href="Text/page.xhtml" media-type="application/xhtml+xml"/>
    <item id="page-image" href="Images/page.jpg" media-type="image/jpeg"/>
  </manifest>
  <spine><itemref idref="cover-page"/><itemref idref="page"/></spine>
</package>'''
    cover_xhtml = b'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><meta name="viewport" content="width=10, height=10"/></head>
<body><img width="10" height="10" src="../Images/cover.jpg"/></body></html>'''
    page_xhtml = b'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><meta name="viewport" content="width=10, height=10"/></head>
<body><img width="100" height="100" src="../Images/page.jpg"/>
<div><img width="100" height="100" src="../Images/page.jpg"/></div></body></html>'''
    cover = Image.new("RGB", (10, 10), "red")
    page = Image.new("RGB", (100, 150), "white")
    for x in range(20, 80):
        for y in range(20, 130):
            page.putpixel((x, y), (0, 0, 0))

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/Text/cover.xhtml", cover_xhtml)
        archive.writestr("OEBPS/Text/page.xhtml", page_xhtml)
        archive.writestr("OEBPS/Images/cover.jpg", _jpeg_bytes(cover))
        archive.writestr("OEBPS/Images/page.jpg", _jpeg_bytes(page))


def test_canvas_config_rejects_unusable_margins():
    with pytest.raises(CanvasError, match="usable height"):
        CanvasConfig(top_margin_pct=60, bottom_margin_pct=40)

    with pytest.raises(CanvasError, match="between"):
        CanvasConfig(left_margin_pct=-1)


def test_fit_image_to_canvas_uses_independent_margins_and_preserves_background():
    source = Image.new("L", (100, 100), 255)
    for x in range(20, 80):
        for y in range(20, 80):
            source.putpixel((x, y), 0)

    config = CanvasConfig(
        enabled=True,
        top_margin_pct=10,
        bottom_margin_pct=20,
        left_margin_pct=5,
        right_margin_pct=15,
    )
    result = fit_image_to_canvas(source, (200, 300), config)

    assert result.size == (200, 300)
    assert result.getpixel((0, 0)) == 255
    dark_bbox = ImageOps.invert(result).getbbox()
    assert dark_bbox is not None
    assert dark_bbox[0] >= 10
    assert dark_bbox[1] >= 30
    assert dark_bbox[2] <= 170
    assert dark_bbox[3] <= 240


def test_normalize_epub_updates_content_images_and_panel_view(tmp_path: Path):
    epub = tmp_path / "fixture.epub"
    _write_fixture_epub(epub)
    config = CanvasConfig(enabled=True, top_margin_pct=8, bottom_margin_pct=8, left_margin_pct=3, right_margin_pct=3)

    normalize_epub(epub, config, profile="K11", hq=False)

    with zipfile.ZipFile(epub) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED

        with Image.open(BytesIO(archive.read("OEBPS/Images/page.jpg"))) as page:
            assert page.size == (1072, 1448)
        with Image.open(BytesIO(archive.read("OEBPS/Images/cover.jpg"))) as cover:
            assert cover.size == (10, 10)

        page_xml = ET.fromstring(archive.read("OEBPS/Text/page.xhtml"))
        images = [node for node in page_xml.iter() if node.tag.endswith("img")]
        assert len(images) == 2
        assert all(node.get("width") == "1072" for node in images)
        assert all(node.get("height") == "1448" for node in images)
        viewport = next(node for node in page_xml.iter() if node.tag.endswith("meta"))
        assert viewport.get("content") == "width=1072, height=1448"


def test_normalize_epub_is_noop_when_disabled(tmp_path: Path):
    epub = tmp_path / "fixture.epub"
    _write_fixture_epub(epub)
    before = epub.read_bytes()

    normalize_epub(epub, CanvasConfig(enabled=False), profile="K11")

    assert epub.read_bytes() == before
