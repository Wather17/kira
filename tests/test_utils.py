import tempfile
from pathlib import Path
from PIL import Image
from kira.utils import (
    natural_sort_filenames,
    get_image_files,
    create_cbz_archive,
    resolve_google_drive_path
)


def test_natural_sort_filenames():
    files = ["page_10.jpg", "page_1.jpg", "page_2.jpg", "page_20.jpg"]
    sorted_files = natural_sort_filenames(files)
    assert sorted_files == ["page_1.jpg", "page_2.jpg", "page_10.jpg", "page_20.jpg"]


def test_get_image_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "01.png").touch()
        (tmp_path / "02.jpg").touch()
        (tmp_path / "notes.txt").touch()

        imgs = get_image_files(tmp_path)
        assert len(imgs) == 2
        assert imgs[0].name == "01.png"
        assert imgs[1].name == "02.jpg"


def test_create_cbz_archive():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        img_dir = tmp_path / "manga_pages"
        img_dir.mkdir()

        # Create dummy PIL image
        img = Image.new('RGB', (100, 100), color='white')
        img.save(img_dir / "01.jpg")
        img.save(img_dir / "02.jpg")

        cbz_file = tmp_path / "output.cbz"
        res_file = create_cbz_archive(img_dir, cbz_file)
        assert res_file.exists()
        assert res_file.stat().st_size > 0


def test_resolve_google_drive_path():
    p = resolve_google_drive_path("manga/vol1")
    assert isinstance(p, Path)
