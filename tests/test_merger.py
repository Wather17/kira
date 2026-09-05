import tempfile
from pathlib import Path
from PIL import Image
from kira.merger import VolumeMerger
from kira.utils import create_cbz_archive


def test_volume_merger():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()

        # Create dummy chapter CBZs (Ch 1 and Ch 2)
        for ch in [1, 2]:
            ch_folder = chapters_dir / f"chapter_{ch}"
            ch_folder.mkdir()
            img = Image.new('RGB', (100, 100), color='white')
            img.save(ch_folder / "01.png")
            img.save(ch_folder / "02.png")
            create_cbz_archive(ch_folder, chapters_dir / f"Chapter_{ch:02d}.cbz")

        out_dir = tmp_path / "volumes_out"

        # Custom mapping: Vol 1 contains Ch 1 & 2
        custom_map = {1: [1, 2]}
        merger = VolumeMerger(manga_title="TestManga")
        res_files = merger.merge_all_volumes(chapters_dir, out_dir, mapping=custom_map)

        assert len(res_files) == 1
        assert res_files[0].exists()
        assert res_files[0].name == "TestManga_Vol_01.cbz"


def test_auto_detect_manga_title():
    from kira.merger import auto_detect_manga_title
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_folder = tmp_path / "Chainsaw_Man"
        manga_folder.mkdir()
        
        # Test 1: Folder name detection
        assert auto_detect_manga_title(manga_folder) == "Chainsaw Man"
        
        # Test 2: Chapter filename detection inside generic folder
        gen_folder = tmp_path / "chapters"
        gen_folder.mkdir()
        (gen_folder / "Vinland_Saga_Ch_001.cbz").touch()
        assert auto_detect_manga_title(gen_folder) == "Vinland Saga"


def test_merge_all_volumes_resolves_apis_once_per_run(monkeypatch):
    from kira.providers import OnlineMangaProvider

    search_calls = []
    covers_calls = []

    def fake_search(title):
        search_calls.append(title)
        return {"author": "Test Author"}

    def fake_covers(title):
        covers_calls.append(title)
        return {1: "http://cover.example/vol1.jpg", 2: "http://cover.example/vol2.jpg"}

    monkeypatch.setattr(OnlineMangaProvider, "search_manga_metadata", classmethod(lambda cls, t: fake_search(t)))
    monkeypatch.setattr(OnlineMangaProvider, "fetch_volume_covers", classmethod(lambda cls, t: fake_covers(t)))
    monkeypatch.setattr(OnlineMangaProvider, "download_image", classmethod(lambda cls, u, p: False))

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        for ch in [1, 2, 3, 4]:
            ch_folder = chapters_dir / f"chapter_{ch}"
            ch_folder.mkdir()
            img = Image.new('RGB', (10, 10), color='white')
            img.save(ch_folder / "01.png")
            create_cbz_archive(ch_folder, chapters_dir / f"Chapter_{ch:02d}.cbz")

        out_dir = tmp_path / "volumes_out"
        custom_map = {1: [1, 2], 2: [3, 4]}
        merger = VolumeMerger(manga_title="TestManga")
        res_files = merger.merge_all_volumes(chapters_dir, out_dir, mapping=custom_map)

        assert len(res_files) == 2
        assert len(search_calls) == 1
        assert len(covers_calls) == 1


def test_merge_all_volumes_does_not_use_aot_mapping_when_api_fails(monkeypatch):
    from kira.providers import OnlineMangaProvider

    monkeypatch.setattr(
        OnlineMangaProvider,
        "fetch_volume_chapter_mapping",
        classmethod(lambda cls, title: None),
    )
    monkeypatch.setattr(
        OnlineMangaProvider,
        "search_manga_metadata",
        classmethod(lambda cls, title: None),
    )
    monkeypatch.setattr(
        OnlineMangaProvider,
        "fetch_volume_covers",
        classmethod(lambda cls, title: {}),
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "Death_Note_Ch_01.cbz").touch()

        merger = VolumeMerger(manga_title="Death Note")
        result = merger.merge_all_volumes(chapters_dir, tmp_path / "output")

    assert result == []


def test_find_chapter_files_ignores_volume_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "Chapter_01.cbz").touch()
        (chapters_dir / "Vol_01.cbz").touch()
        (chapters_dir / "Volume 1.cbz").touch()

        merger = VolumeMerger(manga_title="TestManga")
        files = merger.find_chapter_files(chapters_dir, 1)
        assert [f.name for f in files] == ["Chapter_01.cbz"]


def test_find_chapter_files_requires_explicit_marker():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "0001.jpg").touch()
        (chapters_dir / "01.jpg").touch()

        merger = VolumeMerger(manga_title="TestManga")
        assert merger.find_chapter_files(chapters_dir, 1) == []


def test_find_chapter_files_strict_number_formats():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "#001.cbz").touch()
        (chapters_dir / "(001).cbz").touch()
        (chapters_dir / "[001].cbz").touch()
        (chapters_dir / "#013.cbz").touch()

        merger = VolumeMerger(manga_title="TestManga")
        files = {f.name for f in merger.find_chapter_files(chapters_dir, 1)}
        assert files == {"#001.cbz", "(001).cbz", "[001].cbz"}
        assert {f.name for f in merger.find_chapter_files(chapters_dir, 13)} == {"#013.cbz"}


def test_find_chapter_files_legit_names_still_match():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        (chapters_dir / "Chapter_01.cbz").touch()
        (chapters_dir / "Ch 13.5.zip").touch()
        (chapters_dir / "chapter_1").mkdir()

        merger = VolumeMerger(manga_title="TestManga")
        assert {f.name for f in merger.find_chapter_files(chapters_dir, 1)} == {"Chapter_01.cbz", "chapter_1"}
        assert {f.name for f in merger.find_chapter_files(chapters_dir, 13)} == {"Ch 13.5.zip"}
