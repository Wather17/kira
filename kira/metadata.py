import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union
import shutil
from kira.utils import get_image_files

class MangaMetadata:
    """Manages metadata generation (ComicInfo.xml) and cover optimization for Kindle eBooks."""

    def __init__(
        self,
        title: str,
        series: str,
        number: Optional[Union[int, str]] = None,
        author: str = "Unknown",
        summary: Optional[str] = None,
        manga: bool = True
    ):
        self.title = title
        self.series = series
        self.number = str(number) if number is not None else ""
        self.author = author
        self.summary = summary or f"{series} Volume {number}" if number else series
        self.manga = manga

    def to_xml(self) -> str:
        """Generate official ComicInfo.xml metadata block."""
        root = ET.Element("ComicInfo")
        
        ET.SubElement(root, "Title").text = self.title
        ET.SubElement(root, "Series").text = self.series
        if self.number:
            ET.SubElement(root, "Number").text = self.number
        ET.SubElement(root, "Writer").text = self.author
        ET.SubElement(root, "Penciller").text = self.author
        ET.SubElement(root, "Summary").text = self.summary
        ET.SubElement(root, "Manga").text = "YesAndRightToLeft" if self.manga else "No"
        
        # Pretty print XML
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def write_comic_info(self, target_dir: Path) -> Path:
        """Write ComicInfo.xml to a target volume directory."""
        target_dir = Path(target_dir)
        xml_path = target_dir / "ComicInfo.xml"
        xml_content = self.to_xml()
        xml_path.write_text(xml_content, encoding="utf-8")
        return xml_path


def set_custom_cover(volume_dir: Union[str, Path], cover_image_path: Union[str, Path]) -> Path:
    """
    Set a custom high-res front cover for a volume directory.
    Renames/pre-pends the cover image as 0000_cover.jpg so KCC & Kindle use it as main thumbnail.
    """
    volume_dir = Path(volume_dir)
    cover_image_path = Path(cover_image_path)

    if not cover_image_path.exists():
        raise FileNotFoundError(f"Cover image not found: {cover_image_path}")

    ext = cover_image_path.suffix.lower()
    target_cover = volume_dir / f"0000_cover{ext}"
    shutil.copy2(cover_image_path, target_cover)
    return target_cover


def optimize_volume_structure(
    volume_dir: Union[str, Path],
    series_name: str,
    volume_number: Optional[int] = None,
    author: str = "Unknown",
    custom_cover: Optional[Union[str, Path]] = None
) -> Path:
    """
    Apply commercial Kindle manga optimization to a volume directory:
    1. Sets explicit cover (0000_cover.ext)
    2. Writes ComicInfo.xml metadata file
    """
    volume_dir = Path(volume_dir)

    if custom_cover:
        set_custom_cover(volume_dir, custom_cover)

    # Generate metadata
    vol_title = f"{series_name} Vol. {volume_number:02d}" if volume_number else series_name
    meta = MangaMetadata(
        title=vol_title,
        series=series_name,
        number=volume_number,
        author=author,
        manga=True
    )
    meta.write_comic_info(volume_dir)

    return volume_dir
