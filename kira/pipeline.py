import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Union


from kira.converter import KindleConverter
from kira.extractor import MangaExtractor
from kira.upscaler import MangaUpscaler
from kira.utils import (
    SUPPORTED_ARCHIVE_EXTS,
    get_image_files,
    get_safe_temp_dir,
    is_colab,
    resolve_google_drive_path,
)


class MangaPipeline:
    """End-to-end processing pipeline for upscaling manga with Real-ESRGAN and converting for Kindle e-readers."""

    def __init__(
        self,
        # Upscaler params
        model_name: str = 'RealESRGAN_x4plus_anime_6B',
        scale: int = 4,
        tile: int = 400,
        half: Optional[bool] = None,
        device: Optional[str] = None,
        grayscale: bool = False,
        max_dimension: Optional[int] = 2400,
        # Kindle Converter params
        kindle_profile: str = 'K11',
        output_format: str = 'EPUB',
        manga_style: bool = True,

        gamma: float = 1.0,
        hq: bool = True,
        cropping: int = 0,
        # Pipeline options
        keep_extracted: bool = False,
        keep_upscaled_cbz: bool = True,
        verbose: bool = False,
        workers: int = 2,
    ):
        self.upscaler = MangaUpscaler(
            model_name=model_name,
            scale=scale,
            tile=tile,
            half=half,
            device=device,
            grayscale=grayscale,
            max_dimension=max_dimension,
            verbose=verbose,
            workers=workers,
        )

        self.converter = KindleConverter(
            profile=kindle_profile,
            output_format=output_format,
            manga_style=manga_style,
            gamma=gamma,
            hq=hq,
            cropping=cropping,
        )

        self.keep_extracted = keep_extracted
        self.keep_upscaled_cbz = keep_upscaled_cbz

    def process_item(
        self,
        input_item: Union[str, Path],
        output_dir: Union[str, Path],
        temp_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Union[str, Path, int, float]]:
        """
        Process a single manga archive or image directory.

        Steps:
            1. Extract pages (CBZ, ZIP, CBR, RAR, or directory)
            2. Upscale images with Real-ESRGAN
            3. Convert upscaled images to Kindle format (EPUB/MOBI/AZW3) via KCC
        """
        start_time = time.time()
        input_path = resolve_google_drive_path(str(input_item))
        out_dir = resolve_google_drive_path(str(output_dir))
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[Kira Pipeline] Starting processing for: {input_path.name}")

        work_dir = Path(temp_dir) if temp_dir else get_safe_temp_dir("work")
        extracted_dir = work_dir / "extracted"
        upscaled_dir = work_dir / "upscaled"

        extractor = MangaExtractor(temp_dir=extracted_dir)

        try:
            # 1. Extract
            extracted_path, raw_images = extractor.extract(input_path)

            # Check if extracted archive was a bundle containing multiple chapters
            nested_items = [
                f for f in extracted_path.iterdir()
                if (f.is_file() and f.suffix.lower() in SUPPORTED_ARCHIVE_EXTS) or
                   (f.is_dir() and get_image_files(f, recursive=False))
            ]
            has_direct_images = bool(get_image_files(extracted_path, recursive=False))

            if not has_direct_images and len(nested_items) >= 2:
                print(f"[Kira Pipeline] '{input_path.name}' is a chapter bundle ({len(nested_items)} chapters). Auto-merging into official volumes...")
                from kira.merger import VolumeMerger
                merger = VolumeMerger()
                merged_vols_dir = work_dir / "merged_volumes"
                volume_files = merger.merge_all_volumes(extracted_path, merged_vols_dir)
                last_stat = {}
                for vol_idx, vol_file in enumerate(volume_files, 1):
                    print(f"\n[Kira Pipeline] Processing Auto-Merged Volume [{vol_idx}/{len(volume_files)}]: {vol_file.name}")
                    last_stat = self.process_item(vol_file, out_dir)
                return last_stat

            page_count = len(raw_images)
            print(f"[Kira Pipeline] Extracted {page_count} pages.")

            # 2. Upscale
            upscaled_images = self.upscaler.upscale_batch(raw_images, upscaled_dir)

            # Option to output upscaled CBZ alongside Kindle file
            if self.keep_upscaled_cbz and self.converter.output_format != 'CBZ':
                upscaled_cbz_dir = out_dir / "upscaled_cbz"
                upscaled_cbz_dir.mkdir(parents=True, exist_ok=True)
                from kira.utils import create_cbz_archive
                create_cbz_archive(upscaled_dir, upscaled_cbz_dir / f"{input_path.stem}_upscaled.cbz")

            # 3. Kindle Convert
            kindle_output_file = self.converter.convert(
                input_path=upscaled_dir,
                output_dir=out_dir,
                title=input_path.stem
            )
            used_fallback = getattr(self.converter, 'last_fallback', False)
            if used_fallback:
                print("[Kira Pipeline Warning] KCC conversion failed or unavailable; output is a plain CBZ (not Kindle-adapted).")

            elapsed = time.time() - start_time
            file_size_mb = kindle_output_file.stat().st_size / (1024 * 1024) if kindle_output_file.exists() and kindle_output_file.is_file() else 0.0

            stats = {
                'title': input_path.stem,
                'input': str(input_path),
                'output': str(kindle_output_file),
                'pages': page_count,
                'time_seconds': round(elapsed, 2),
                'size_mb': round(file_size_mb, 2),
                'status': 'fallback' if used_fallback else 'ok'
            }

            print(f"[Kira Pipeline] Completed '{input_path.stem}' in {elapsed:.1f}s -> {kindle_output_file.name} ({file_size_mb:.2f} MB)")
            return stats

        finally:
            # Clean up temporary work directory
            if not self.keep_extracted and work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)

    def process_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path]
    ) -> List[Dict[str, Union[str, Path, int, float]]]:
        """
        Process all manga archives or image folders inside an input directory.
        """
        in_path = resolve_google_drive_path(str(input_dir))
        out_path = resolve_google_drive_path(str(output_dir))
        out_path.mkdir(parents=True, exist_ok=True)

        if not in_path.exists():
            raise FileNotFoundError(f"Input directory not found: {in_path}")

        # Scan for supported archives or subdirectories
        items_to_process = []
        for entry in in_path.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_ARCHIVE_EXTS:
                items_to_process.append(entry)
            elif entry.is_dir() and get_image_files(entry, recursive=False):
                items_to_process.append(entry)

        from kira.utils import natural_sort_filenames
        items_to_process = natural_sort_filenames(items_to_process)

        if not items_to_process:
            print(f"[Kira Pipeline Warning] No manga archives or image folders found in {in_path}")
            return []

        # Check if the folder contains loose chapters that should be merged into volumes first
        is_chapters = any(re.search(r"(?:ch|chapter|cap|c)[\s_\-\.]*\d+", item.name, re.IGNORECASE) for item in items_to_process)
        if is_chapters and len(items_to_process) >= 2:
            print(f"\n[Kira Pipeline] Detected {len(items_to_process)} chapter files in {in_path}. Auto-merging into official volumes with covers & metadata...")
            from kira.merger import VolumeMerger
            merger = VolumeMerger()
            merged_vols_dir = get_safe_temp_dir("auto_merged_vols")
            volume_files = merger.merge_all_volumes(in_path, merged_vols_dir)
            if volume_files:
                items_to_process = volume_files

        print(f"\n==================================================")
        print(f" Kira Manga Pipeline - Batch Processing ({len(items_to_process)} items)")
        print(f" Input:  {in_path}")
        print(f" Output: {out_path}")
        print(f" Device: {self.upscaler.device_str} | Model: {self.upscaler.model_name}")
        print(f" Target: Kindle ({self.converter.profile}) -> {self.converter.output_format}")
        print(f"==================================================\n")

        results = []
        for idx, item in enumerate(items_to_process, 1):
            print(f"\n--- Processing Item [{idx}/{len(items_to_process)}]: {item.name} ---")
            try:
                stat = self.process_item(item, out_path)
                if stat:
                    results.append(stat)
            except Exception as e:
                print(f"[Kira Pipeline Error] Failed to process '{item.name}': {e}")

        return results

