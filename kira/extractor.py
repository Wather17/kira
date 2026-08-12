import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple, Union

try:
    import rarfile
except ImportError:
    rarfile = None

from kira.utils import SUPPORTED_ARCHIVE_EXTS, get_image_files, get_safe_temp_dir, natural_sort_filenames


class MangaExtractor:
    """Handles unpacking manga archives (CBZ, ZIP, CBR, RAR) or directory scans."""

    def __init__(self, temp_dir: Optional[Union[str, Path]] = None):
        self.temp_dir = Path(temp_dir) if temp_dir else get_safe_temp_dir("extracted")
        self.temp_dir.mkdir(parents=True, exist_ok=True)


    def extract(self, source_path: Union[str, Path]) -> Tuple[Path, List[Path]]:
        """
        Extract archive or validate directory of manga pages.

        Returns:
            Tuple[Path, List[Path]]: (target_directory, list_of_naturally_sorted_image_paths)
        """
        source = Path(source_path).resolve()

        if not source.exists():
            raise FileNotFoundError(f"Input path does not exist: {source}")

        if source.is_dir():
            images = get_image_files(source)
            if not images:
                raise ValueError(f"Directory {source} contains no valid image files.")
            return source, images

        suffix = source.suffix.lower()
        if suffix not in SUPPORTED_ARCHIVE_EXTS:
            raise ValueError(f"Unsupported archive format: {suffix}. Supported: {SUPPORTED_ARCHIVE_EXTS}")

        target_dir = self.temp_dir / source.stem
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        if suffix in ('.cbz', '.zip'):
            self._extract_zip(source, target_dir)
        elif suffix in ('.cbr', '.rar'):
            self._extract_rar(source, target_dir)

        images = get_image_files(target_dir)
        if not images:
            raise ValueError(f"Extracted archive {source} contained no valid images.")

        return target_dir, images

    def _extract_zip(self, zip_path: Path, output_dir: Path) -> None:
        """Extract ZIP / CBZ archive using Python built-in zipfile."""
        with zipfile.ZipFile(zip_path, 'r') as archive:
            archive.extractall(output_dir)

    def _extract_rar(self, rar_path: Path, output_dir: Path) -> None:
        """Extract RAR / CBR archive using rarfile or 7z system binary fallback."""
        extracted = False
        if rarfile is not None:
            try:
                with rarfile.RarFile(rar_path, 'r') as archive:
                    archive.extractall(output_dir)
                extracted = True
            except Exception:
                extracted = False

        if not extracted:
            # Fallback to system 7z binary if available
            seven_zip = shutil.which('7z') or shutil.which('7za') or shutil.which('unrar')
            if seven_zip:
                cmd = [seven_zip, 'x', '-y', f'-o{output_dir}', str(rar_path)]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    extracted = True

        if not extracted:
            raise RuntimeError(
                f"Failed to extract RAR archive {rar_path}. Please install `unrar` or `p7zip-full`."
            )

    def cleanup(self, path: Optional[Path] = None) -> None:
        """Clean up extracted temporary files."""
        target = path or self.temp_dir
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
