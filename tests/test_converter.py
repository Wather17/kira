import tempfile
from pathlib import Path
from PIL import Image
from kira.converter import KindleConverter


def test_kindle_converter_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "upscaled_manga"
        manga_dir.mkdir()

        img = Image.new('RGB', (100, 100), color='white')
        img.save(manga_dir / "0001.jpg")

        converter = KindleConverter(profile='KPW5', output_format='CBZ')
        out_dir = tmp_path / "kindle_out"
        res_file = converter.convert(manga_dir, out_dir, title="TestManga")

        assert res_file.exists()
        assert res_file.suffix.lower() == ".cbz"


def test_kindle_converter_defaults_and_legacy_mapping():
    # Default format is EPUB
    conv_default = KindleConverter()
    assert conv_default.output_format == "EPUB"

    # AZW3 maps to EPUB
    conv_azw3 = KindleConverter(output_format="AZW3")
    assert conv_azw3.output_format == "EPUB"

    # MOBI maps to EPUB
    conv_mobi = KindleConverter(output_format="MOBI")
    assert conv_mobi.output_format == "EPUB"

