import tempfile
from pathlib import Path
from PIL import Image
from kira.metadata import MangaMetadata, set_custom_cover, optimize_volume_structure

def test_manga_metadata_xml_generation():
    meta = MangaMetadata(
        title="Attack on Titan Vol. 01",
        series="Attack on Titan",
        number=1,
        author="Hajime Isayama",
        manga=True
    )
    xml_str = meta.to_xml()
    assert "<Title>Attack on Titan Vol. 01</Title>" in xml_str
    assert "<Series>Attack on Titan</Series>" in xml_str
    assert "<Writer>Hajime Isayama</Writer>" in xml_str
    assert "<Manga>YesAndRightToLeft</Manga>" in xml_str


def test_optimize_volume_structure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        vol_dir = Path(tmp_dir) / "vol_01"
        vol_dir.mkdir()
        
        cover_src = Path(tmp_dir) / "my_cover.jpg"
        Image.new("RGB", (300, 400), color="blue").save(cover_src)
        
        optimize_volume_structure(
            vol_dir,
            series_name="Monster",
            volume_number=1,
            author="Naoki Urasawa",
            custom_cover=cover_src
        )
        
        assert (vol_dir / "0000_cover.jpg").exists()
        assert (vol_dir / "ComicInfo.xml").exists()
        
        xml_content = (vol_dir / "ComicInfo.xml").read_text(encoding="utf-8")
        assert "Monster Vol. 01" in xml_content
        assert "Naoki Urasawa" in xml_content
