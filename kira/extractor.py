import os
import shutil
import stat
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

MAX_ZIP_ENTRIES = 100_000
MAX_TOTAL_UNCOMPRESSED_BYTES = 40 * 1024**3


class MangaExtractor:
    """Handles unpacking manga archives (CBZ, ZIP, CBR, RAR) or directory scans."""

    def __init__(
        self,
        temp_dir: Optional[Union[str, Path]] = None,
        max_zip_entries: int = MAX_ZIP_ENTRIES,
        max_total_uncompressed: int = MAX_TOTAL_UNCOMPRESSED_BYTES,
    ):
        self.temp_dir = Path(temp_dir) if temp_dir else get_safe_temp_dir("extracted")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_zip_entries = max_zip_entries
        self.max_total_uncompressed = max_total_uncompressed


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
        
        # Check for single nested directory wrapper (e.g. Attack on Titan/...)
        children = list(target_dir.iterdir())
        if len(children) == 1 and children[0].is_dir():
            target_dir = children[0]
            images = get_image_files(target_dir)

        # Check for nested chapter archives
        nested_archives = [
            f for f in target_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_ARCHIVE_EXTS
        ]
        if not images and not nested_archives:
            raise ValueError(f"Extracted archive {source} contained no valid images or chapter archives.")

        return target_dir, images


    def _validate_zip_member(self, member: zipfile.ZipInfo) -> None:
        """Reject archive members with unsafe paths or symlinks."""
        self._validate_archive_member(member.filename, bool(member.external_attr >> 16 and stat.S_ISLNK(member.external_attr >> 16)))

    def _validate_archive_member(self, filename: str, is_symlink: bool = False) -> None:
        """Reject archive members with unsafe paths or symlinks."""
        name = filename.replace("\\", "/")
        if name.startswith("/") or os.path.isabs(filename):
            raise ValueError(
                f"Archive entry {filename!r} rejected: absolute path is not allowed."
            )
        normalized = Path(os.path.normpath(name))
        if ".." in normalized.parts or ".." in name.split("/"):
            raise ValueError(
                f"Archive entry {filename!r} rejected: path traversal is not allowed."
            )
        if is_symlink:
            raise ValueError(
                f"Archive entry {filename!r} rejected: symlink entries are not allowed."
            )

    def _extract_zip(self, zip_path: Path, output_dir: Path) -> None:
        """Extract ZIP / CBZ archive safely, validating member paths and limits."""
        with zipfile.ZipFile(zip_path, 'r') as archive:
            members = archive.infolist()
            if len(members) > self.max_zip_entries:
                raise ValueError(
                    f"Archive {zip_path.name} rejected: {len(members)} entries exceeds "
                    f"the limit of {self.max_zip_entries}."
                )
            total_size = 0
            for member in members:
                self._validate_zip_member(member)
                total_size += member.file_size
            if total_size > self.max_total_uncompressed:
                raise ValueError(
                    f"Archive {zip_path.name} rejected: uncompressed size {total_size} bytes "
                    f"exceeds the limit of {self.max_total_uncompressed} bytes."
                )
            for member in members:
                archive.extract(member, output_dir)

    def _extract_rar(self, rar_path: Path, output_dir: Path) -> None:
        """Extract RAR / CBR archive using rarfile or 7z system binary fallback."""
        if rarfile is not None:
            try:
                with rarfile.RarFile(rar_path, 'r') as archive:
                    self._validate_rar_members(archive.infolist(), rar_path)
                    archive.extractall(output_dir)
                return
            except ValueError:
                raise
            except Exception:
                pass

        # Fallback to system 7z binary if available. List before extracting so
        # the same entry and uncompressed-size limits apply to both backends.
        seven_zip = shutil.which('7z') or shutil.which('7za') or shutil.which('unrar')
        if seven_zip:
            self._validate_7z_listing(seven_zip, rar_path)
            cmd = [seven_zip, 'x', '-y', f'-o{output_dir}', str(rar_path)]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                return

        raise RuntimeError(
            f"Failed to extract RAR archive {rar_path}. Please install `unrar` or `p7zip-full`."
        )

    def _validate_rar_members(self, members: List[object], rar_path: Path) -> None:
        """Validate RAR metadata before any member is written to disk."""
        if len(members) > self.max_zip_entries:
            raise ValueError(
                f"Archive {rar_path.name} rejected: {len(members)} entries exceeds "
                f"the limit of {self.max_zip_entries}."
            )

        total_size = 0
        for member in members:
            filename = str(getattr(member, "filename", ""))
            self._validate_archive_member(
                filename,
                bool(getattr(member, "is_symlink", lambda: False)()),
            )
            total_size += int(getattr(member, "file_size", 0))

        if total_size > self.max_total_uncompressed:
            raise ValueError(
                f"Archive {rar_path.name} rejected: uncompressed size {total_size} bytes "
                f"exceeds the limit of {self.max_total_uncompressed} bytes."
            )

    def _validate_7z_listing(self, seven_zip: str, rar_path: Path) -> None:
        """List a 7z-compatible archive and validate metadata before extraction."""
        res = subprocess.run(
            [seven_zip, 'l', '-slt', str(rar_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to inspect RAR archive {rar_path} with {seven_zip}.")

        members = []
        listing = res.stdout.split("----------")[-1]
        for block in listing.split("\n\n"):
            fields = {}
            for line in block.splitlines():
                key, separator, value = line.partition(" = ")
                if separator:
                    fields[key] = value
            if "Path" not in fields or "Size" not in fields:
                continue
            members.append(
                type("SevenZipMember", (), {
                    "filename": fields["Path"],
                    "file_size": int(fields["Size"]),
                    "is_symlink": lambda self, symlink="l" in fields.get("Attributes", "").lower(): symlink,
                })()
            )

        self._validate_rar_members(members, rar_path)

    def cleanup(self, path: Optional[Path] = None) -> None:
        """Clean up extracted temporary files."""
        target = path or self.temp_dir
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
