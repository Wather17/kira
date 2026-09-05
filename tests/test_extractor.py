import io
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import pytest
from kira.extractor import MangaExtractor
from kira.utils import create_cbz_archive


def _make_cbz(path: Path, entries: dict) -> None:
    with zipfile.ZipFile(path, 'w') as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


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


def test_extractor_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_file = tmp_path / "evil.cbz"
        _make_cbz(cbz_file, {"../evil.txt": b"payload"})

        extractor = MangaExtractor(temp_dir=tmp_path / "out")
        with pytest.raises(ValueError, match="path traversal"):
            extractor.extract(cbz_file)
        assert not (tmp_path / "evil.txt").exists()


def test_extractor_rejects_absolute_path_entry():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_file = tmp_path / "evil.cbz"
        _make_cbz(cbz_file, {"/etc/evil.txt": b"payload"})

        extractor = MangaExtractor(temp_dir=tmp_path / "out")
        with pytest.raises(ValueError, match="absolute path"):
            extractor.extract(cbz_file)


def test_extractor_rejects_backslash_traversal():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_file = tmp_path / "evil.cbz"
        _make_cbz(cbz_file, {"..\\evil.txt": b"payload"})

        extractor = MangaExtractor(temp_dir=tmp_path / "out")
        with pytest.raises(ValueError, match="path traversal"):
            extractor.extract(cbz_file)


def test_extractor_rejects_symlink_entry():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_file = tmp_path / "evil.cbz"
        info = zipfile.ZipInfo("page.jpg")
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(cbz_file, 'w') as zf:
            zf.writestr(info, b"data")

        extractor = MangaExtractor(temp_dir=tmp_path / "out")
        with pytest.raises(ValueError, match="symlink"):
            extractor.extract(cbz_file)


def test_extractor_rejects_zip_bomb_size():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_file = tmp_path / "bomb.cbz"
        _make_cbz(cbz_file, {"01.jpg": b"x" * 100})

        extractor = MangaExtractor(temp_dir=tmp_path / "out", max_total_uncompressed=10)
        with pytest.raises(ValueError, match="uncompressed size"):
            extractor.extract(cbz_file)


@pytest.mark.parametrize(
    ("members", "limit", "message"),
    [
        ([SimpleNamespace(filename="01.jpg", file_size=1, is_symlink=lambda: False)] * 2, 1, "entries"),
        ([SimpleNamespace(filename="01.jpg", file_size=11, is_symlink=lambda: False)], 10, "uncompressed size"),
    ],
)
def test_extractor_rejects_rar_limits_before_extraction(monkeypatch, members, limit, message):
    class FakeArchive:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def infolist(self):
            return members

        def extractall(self, output_dir):
            raise AssertionError("RAR extraction must not start after preflight rejection")

    fake_rarfile = SimpleNamespace(RarFile=lambda path, mode: FakeArchive())
    monkeypatch.setattr("kira.extractor.rarfile", fake_rarfile)

    extractor = MangaExtractor(max_zip_entries=limit, max_total_uncompressed=10)
    with pytest.raises(ValueError, match=message):
        extractor._extract_rar(Path("unsafe.rar"), Path("output"))


def test_extractor_rar_7z_preflight_rejects_before_extract(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "l":
            return SimpleNamespace(
                returncode=0,
                stdout="----------\nPath = page.jpg\nSize = 11\nAttributes = .....\n",
                stderr="",
            )
        raise AssertionError("7z extraction must not start after preflight rejection")

    monkeypatch.setattr("kira.extractor.rarfile", None)
    monkeypatch.setattr("kira.extractor.shutil.which", lambda name: "/usr/bin/7z")
    monkeypatch.setattr("kira.extractor.subprocess.run", fake_run)

    extractor = MangaExtractor(max_total_uncompressed=10)
    with pytest.raises(ValueError, match="uncompressed size"):
        extractor._extract_rar(Path("unsafe.rar"), Path("output"))

    assert calls == [["/usr/bin/7z", "l", "-slt", "unsafe.rar"]]


def test_extractor_accepts_legit_cbz():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        img_dir = tmp_path / "pages"
        img_dir.mkdir()
        img = Image.new('RGB', (100, 100), color='white')
        img.save(img_dir / "0001.jpg")
        img.save(img_dir / "0002.jpg")

        cbz_file = tmp_path / "chapter.cbz"
        create_cbz_archive(img_dir, cbz_file)

        extractor = MangaExtractor(temp_dir=tmp_path / "out")
        extracted_dir, pages = extractor.extract(cbz_file)
        assert len(pages) == 2
