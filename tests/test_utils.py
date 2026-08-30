import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from kira.utils import (
    natural_sort_filenames,
    get_image_files,
    create_cbz_archive,
    get_safe_temp_dir,
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


def test_get_safe_temp_dir_colab():
    with patch("kira.utils.os.path.exists", return_value=True), \
         patch("kira.utils.Path.mkdir") as mock_mkdir:
        d = get_safe_temp_dir("work")
    assert str(d).startswith("/content/kira_temp")
    mock_mkdir.assert_called()


def test_get_safe_temp_dir_local():
    with patch("kira.utils.is_colab", return_value=False), \
         patch("kira.utils.Path.resolve", return_value=Path("/tmp/scratch/kira_temp")), \
         patch("kira.utils.Path.mkdir") as mock_mkdir:
        d = get_safe_temp_dir("work")
    assert d.parent.name == "kira_temp"
    assert d.name.startswith("work_")
    mock_mkdir.assert_called()


def test_suppress_stdout_stderr(capsys):
    from kira.utils import suppress_stdout_stderr
    import sys

    # Without suppression
    print("hello visible")
    captured = capsys.readouterr()
    assert "hello visible" in captured.out

    # With suppression enabled
    with suppress_stdout_stderr(enabled=True):
        print("Tile 1/12 should be hidden")
        sys.stderr.write("stderr should be hidden\n")
    captured = capsys.readouterr()
    assert "Tile 1/12" not in captured.out
    assert "stderr should be hidden" not in captured.err

    # With suppression disabled
    with suppress_stdout_stderr(enabled=False):
        print("Tile visible")
    captured = capsys.readouterr()
    assert "Tile visible" in captured.out

