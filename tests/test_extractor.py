import tempfile
from pathlib import Path
from PIL import Image
from kira.extractor import MangaExtractor
from kira.utils import create_cbz_archive


def test_extractor_directory():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        img_dir = tmp_path / "chapter_1"
        img_dir.mkdir()

        img = Image.new('RGB', (100, 100), color='white')
        img.save(img_dir / "page1.jpg")
        img.save(img_dir / "page2.jpg")

        extractor = MangaExtractor()
        out_dir, pages = extractor.extract(img_dir)
        assert out_dir == img_dir
        assert len(pages) == 2


def test_extractor_cbz_archive():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        img_dir = tmp_path / "raw_pages"
        img_dir.mkdir()

        img = Image.new('RGB', (100, 100), color='white')
        img.save(img_dir / "01.jpg")
        img.save(img_dir / "02.jpg")

        cbz_file = tmp_path / "test.cbz"
        create_cbz_archive(img_dir, cbz_file)

        extractor = MangaExtractor()
        extracted_dir, pages = extractor.extract(cbz_file)
        assert extracted_dir.exists()
        assert len(pages) == 2
