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
