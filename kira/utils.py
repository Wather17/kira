import os
import re
import sys
import shutil
import subprocess
import zipfile

from pathlib import Path
from typing import List, Union
from natsort import natsorted

SUPPORTED_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')
SUPPORTED_ARCHIVE_EXTS = ('.cbz', '.zip', '.cbr', '.rar')


def is_colab() -> bool:
    """Check if code is running inside Google Colab environment."""
    return 'google.colab' in sys.modules or os.path.exists('/content')


def natural_sort_filenames(file_list: List[Union[str, Path]]) -> List[Union[str, Path]]:
    """Sort a list of filenames or Path objects naturally (e.g. page_2.jpg before page_10.jpg)."""
    return natsorted(file_list, key=lambda p: str(p))


def get_image_files(directory: Union[str, Path], recursive: bool = True) -> List[Path]:
    """Find all image files in a directory, naturally sorted."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []

    images = []
    pattern = "**/*" if recursive else "*"
    for p in dir_path.glob(pattern):
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS:
            # Skip hidden files or __MACOSX
            if not any(part.startswith('.') or part.startswith('__MACOSX') for part in p.parts):
                images.append(p)

    return natural_sort_filenames(images)


def resolve_google_drive_path(path_str: str) -> Path:
    """
    Resolve Google Drive paths for Colab environment or return absolute Path.
    Handles 'MyDrive/folder', 'Google Drive/folder', '/content/drive/MyDrive/...', etc.
    """
    p = Path(path_str).expanduser()
    
    if is_colab():
        colab_drive_root = Path('/content/drive/MyDrive')
        str_val = str(p)

        if str_val.startswith('/content/drive/MyDrive'):
            return p
        elif str_val.startswith('MyDrive/') or str_val == 'MyDrive':
            rel_part = str_val.replace('MyDrive/', '', 1) if str_val.startswith('MyDrive/') else ''
            return colab_drive_root / rel_part
        elif str_val.startswith('drive/MyDrive/'):
            rel_part = str_val.replace('drive/MyDrive/', '', 1)
            return colab_drive_root / rel_part
        elif not p.is_absolute():
            # Relative path provided, check if Google Drive mounted
            if colab_drive_root.exists():
                return colab_drive_root / p

    return p.resolve()


def get_safe_temp_dir(prefix: str = "kira_temp") -> Path:
    """Get safe temporary directory avoiding small tmpfs RAM disk limits."""
    import tempfile
    if is_colab():
        base = Path("/content/kira_temp")
    else:
        # Use workspace scratch dir if present, else fallback to tempfile
        base = Path("./scratch/kira_temp").resolve()

    target = base / f"{prefix}_{os.getpid()}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_cbz_archive(source_dir: Union[str, Path], output_cbz_path: Union[str, Path]) -> Path:
    """
    Package all images in source_dir into a cleanly formatted CBZ (ZIP) archive.
    """
    source_dir = Path(source_dir)
    output_cbz_path = Path(output_cbz_path)
    output_cbz_path.parent.mkdir(parents=True, exist_ok=True)

    images = get_image_files(source_dir, recursive=True)
    if not images:
        raise ValueError(f"No images found in {source_dir} to package into CBZ.")

    # Create ZIP with .cbz extension
    with zipfile.ZipFile(output_cbz_path, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for idx, img_path in enumerate(images):
            # Maintain clean relative paths or standardized page numbering
            ext = img_path.suffix.lower()
            arcname = f"{idx + 1:04d}{ext}"
            cbz.write(img_path, arcname=arcname)

        # Include ComicInfo.xml if present
        comic_info = source_dir / "ComicInfo.xml"
        if comic_info.exists():
            cbz.write(comic_info, arcname="ComicInfo.xml")

    return output_cbz_path



def is_rclone_installed() -> bool:
    """Check if rclone executable is available in system PATH."""
    return shutil.which("rclone") is not None


def get_rclone_remotes() -> list[str]:
    """List configured rclone remotes."""
    if not is_rclone_installed():
        return []
    try:
        res = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True)
        if res.returncode == 0:
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    except Exception:
        pass
    return []


def rclone_copy(src: Union[str, Path], dst: str, progress: bool = True) -> bool:
    """Execute rclone copy from src to dst remote/path."""
    if not is_rclone_installed():
        print("[Kira Warning] rclone is not installed.")
        return False
    cmd = ["rclone", "copy", str(src), dst]
    if progress:
        cmd.append("-P")
    res = subprocess.run(cmd)
    return res.returncode == 0


