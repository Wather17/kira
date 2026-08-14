import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml

from kira.extractor import MangaExtractor
from kira.utils import create_cbz_archive, get_image_files, natural_sort_filenames

# Default pre-set mapping for Attack on Titan (Shingeki no Kyojin) - Volumes 1 to 34 (Chapters 1 to 139)
AOT_VOLUME_MAPPING: Dict[int, List[int]] = {
    1: [1, 2, 3, 4],
    2: [5, 6, 7, 8, 9],
    3: [10, 11, 12, 13],
    4: [14, 15, 16, 17, 18],
    5: [19, 20, 21, 22],
    6: [23, 24, 25, 26],
    7: [27, 28, 29, 30],
    8: [31, 32, 33, 34],
    9: [35, 36, 37, 38],
    10: [39, 40, 41, 42],
    11: [43, 44, 45, 46],
    12: [47, 48, 49, 50],
    13: [51, 52, 53, 54],
    14: [55, 56, 57, 58],
    15: [59, 60, 61, 62],
    16: [63, 64, 65, 66],
    17: [67, 68, 69, 70],
    18: [71, 72, 73, 74],
    19: [75, 76, 77, 78],
    20: [79, 80, 81, 82],
    21: [83, 84, 85, 86],
    22: [87, 88, 89, 90],
    23: [91, 92, 93, 94],
    24: [95, 96, 97, 98],
    25: [99, 100, 101, 102],
    26: [103, 104, 105, 106],
    27: [107, 108, 109, 110],
    28: [111, 112, 113, 114],
    29: [115, 116, 117, 118],
    30: [119, 120, 121, 122],
    31: [123, 124, 125, 126],
    32: [127, 128, 129, 130],
    33: [131, 132, 133, 134],
    34: [135, 136, 137, 138, 139],
}


def auto_detect_manga_title(chapters_dir: Union[str, Path]) -> str:
    """Automatically detect manga series title from directory name or chapter filenames."""
    path = Path(chapters_dir).resolve()
    generic_names = {"chapters", "chapter", "capitulos", "input", "inputs", "manga", "mangas", "raw", "temp", "cbz", "zip", "scratch"}
    
    # 1. Check folder name first
    dir_name = path.name
    if dir_name.lower() not in generic_names and not dir_name.isdigit():
        clean_dir = re.sub(r"\[.*?\]|\(.*?\)", "", dir_name)
        clean_dir = re.sub(r"[_\.]+", " ", clean_dir).strip()
        if len(clean_dir) > 1:
            return clean_dir

    # 2. Check chapter files inside directory
    try:
        sample_files = [f for f in path.iterdir() if f.is_file() or f.is_dir()][:5]
        for f in sample_files:
            raw_name = f.stem
            clean = re.sub(r"\[.*?\]|\(.*?\)", "", raw_name)
            
            # Format: "Ch. 1 - Attack on Titan"
            m_after = re.search(r"(?:ch|chapter|cap)[\s_\-\.]*\d+[\s_\-\.]*[-–—][\s_\-\.]*(.+)", clean, re.IGNORECASE)
            if m_after:
                title_cand = m_after.group(1).strip()
                if title_cand:
                    return re.sub(r"[_\.]+", " ", title_cand).strip()
                    
            # Format: "Death_Note_Ch_01" or "Monster - Chapter 12"
            clean = re.sub(r"(?:[\s_\-\.]*(?:ch|chapter|cap|capitulo|c|vol|volume)[\s_\-\.]*\d+.*)", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"^(?:unofficial|raw|scan)[\s_\-\.]*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"[_\.]+", " ", clean).strip()
            if len(clean) > 2:
                return clean
    except Exception:
        pass

    return "Manga"


class VolumeMerger:
    """Combines individual chapter files/folders into official Volume CBZ archives."""

    def __init__(self, manga_title: Optional[str] = None):
        self.manga_title = manga_title
        self.extractor = MangaExtractor()


    def load_mapping(self, mapping_source: Union[str, Path, Dict]) -> Dict[int, List[int]]:
        """
        Load chapter-to-volume mapping from JSON file, YAML file, or dictionary.
        Format: { 1: [1, 2, 3, 4], 2: [5, 6, 7, 8, 9], ... }
        """
        if isinstance(mapping_source, dict):
            return {int(k): [int(c) for c in v] for k, v in mapping_source.items()}

        mapping_path = Path(mapping_source)
        if not mapping_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

        content = mapping_path.read_text(encoding='utf-8')
        if mapping_path.suffix.lower() in ('.yaml', '.yml'):
            raw_dict = yaml.safe_load(content)
        else:
            raw_dict = json.loads(content)

        return {int(k): [int(c) for c in v] for k, v in raw_dict.items()}

    def find_chapter_files(self, chapters_dir: Path, chapter_num: Union[int, float]) -> List[Path]:
        """Locate file(s) or folder(s) matching chapter number (e.g. 'Ch. 1', 'ch_01', 'Ch. 13.5')."""
        matches = []
        # Pattern matching exact chapter number or decimal sub-chapters (e.g. 13 and 13.5)
        pat_exact = rf"(?:ch|chapter|cap|capitulo)[\s_\-\.]*0*{chapter_num}(?!\d)"
        pat_sub = rf"(?:ch|chapter|cap|capitulo)[\s_\-\.]*0*{chapter_num}\.\d+"
        pat_num = rf"\b0*{chapter_num}\b"

        for item in natural_sort_filenames(list(chapters_dir.iterdir())):
            name_lower = item.name.lower()
            if re.search(pat_exact, name_lower) or re.search(pat_num, name_lower):
                matches.append(item)
            elif isinstance(chapter_num, int) and re.search(pat_sub, name_lower):
                matches.append(item)

        return matches


    def merge_volume(
        self,
        volume_num: int,
        chapter_nums: List[int],
        chapters_dir: Union[str, Path],
        output_dir: Union[str, Path]
    ) -> Optional[Path]:
        """
        Merge a set of chapter files/folders into a single volume CBZ archive.
        """
        chapters_path = Path(chapters_dir).resolve()
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        from kira.utils import get_safe_temp_dir
        vol_temp = get_safe_temp_dir(f"vol_{volume_num:02d}")


        try:
            global_page_idx = 1
            found_chapters = 0

            for ch_num in chapter_nums:
                ch_files = self.find_chapter_files(chapters_path, ch_num)
                if not ch_files:
                    print(f"[Kira Merger Warning] Chapter {ch_num} for Volume {volume_num} not found in {chapters_path}")
                    continue

                for ch_file in ch_files:
                    found_chapters += 1
                    _, ch_images = self.extractor.extract(ch_file)

                    # Copy images to volume temp dir with ordered sequential names
                    for img_path in ch_images:
                        ext = img_path.suffix.lower()
                        target_name = f"page_{global_page_idx:04d}{ext}"
                        shutil.copy2(img_path, vol_temp / target_name)
                        global_page_idx += 1


            if found_chapters == 0:
                print(f"[Kira Merger] Skipping Volume {volume_num:02d}: No matching chapter files found.")
                return None

            # Apply commercial Kindle metadata and cover optimization before archiving
            from kira.metadata import optimize_volume_structure
            from kira.providers import OnlineMangaProvider

            meta = OnlineMangaProvider.search_manga_metadata(self.manga_title)
            author = meta.get("author", "Unknown") if meta else "Unknown"
            
            # Fetch official volume cover if available
            vol_covers = OnlineMangaProvider.fetch_volume_covers(self.manga_title)
            cover_url = vol_covers.get(volume_num) or (meta.get("cover_url") if (meta and volume_num == 1) else None)
            
            cover_file = None
            if cover_url:
                cover_file = vol_temp / "0000_cover.jpg"
                OnlineMangaProvider.download_image(cover_url, cover_file)


            optimize_volume_structure(
                vol_temp,
                series_name=self.manga_title,
                volume_number=volume_num,
                author=author,
                custom_cover=cover_file if (cover_file and cover_file.exists()) else None
            )


            vol_name = f"{self.manga_title}_Vol_{volume_num:02d}.cbz"
            output_cbz = out_path / vol_name
            res = create_cbz_archive(vol_temp, output_cbz)

            print(f"[Kira Merger] Created {vol_name} ({global_page_idx - 1} pages from {found_chapters} chapters)")
            return res

        finally:
            shutil.rmtree(vol_temp, ignore_errors=True)

    def merge_all_volumes(
        self,
        chapters_dir: Union[str, Path],
        output_dir: Union[str, Path],
        mapping: Optional[Union[Dict[int, List[int]], str, Path]] = None
    ) -> List[Path]:
        """
        Merge all volumes according to mapping. Fetches online volume breakdown automatically if none provided.
        """
        if not self.manga_title:
            self.manga_title = auto_detect_manga_title(chapters_dir)
            print(f"[Kira Merger] Auto-detected Manga Title: '{self.manga_title}'")

        if mapping is None:
            if "attack" in self.manga_title.lower() or "shingeki" in self.manga_title.lower():
                vol_map = AOT_VOLUME_MAPPING
            else:
                from kira.providers import OnlineMangaProvider
                print(f"[Kira Merger] Querying online volume division for '{self.manga_title}'...")
                fetched_map = OnlineMangaProvider.fetch_volume_chapter_mapping(self.manga_title)
                vol_map = fetched_map if fetched_map else AOT_VOLUME_MAPPING

        elif isinstance(mapping, (str, Path)):
            vol_map = self.load_mapping(mapping)
        else:
            vol_map = mapping

        output_files = []
        for vol_num, ch_list in vol_map.items():
            cbz_res = self.merge_volume(vol_num, ch_list, chapters_dir, output_dir)
            if cbz_res:
                output_files.append(cbz_res)

        return output_files

