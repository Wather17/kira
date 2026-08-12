import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

from kira.utils import create_cbz_archive

# Popular Kindle Device Profiles supported by KCC
KINDLE_PROFILES: Dict[str, str] = {
    'KPW5': 'Kindle Paperwhite 5 (11th Gen, 6.8")',
    'KPW3': 'Kindle Paperwhite 3/4 (6")',
    'KPW': 'Kindle Paperwhite 1/2',
    'KO': 'Kindle Oasis (1/2/3)',
    'KS': 'Kindle Scribe (10.2")',
    'K11': 'Kindle Basic (11th Gen 2022)',
    'KV': 'Kindle Voyage',
    'K345': 'Kindle 3/4/5/Touch',
    'OTHER': 'Generic E-Reader'
}

OUTPUT_FORMATS = ['EPUB', 'MOBI', 'AZW3', 'CBZ', 'KFX']


class KindleConverter:
    """Wrapper around KCC (Kindle Comic Converter) for adapting upscaled manga to Kindle e-readers."""

    def __init__(
        self,
        profile: str = 'KPW5',
        output_format: str = 'EPUB',
        manga_style: bool = True,
        gamma: float = 1.0,
        hq: bool = True,
        stretch: bool = False,
        upscale: bool = True,
        webtoon: bool = False,
        color: bool = False,
    ):
        self.profile = profile if profile in KINDLE_PROFILES else 'KPW5'
        self.output_format = output_format.upper() if output_format.upper() in OUTPUT_FORMATS else 'EPUB'
        self.manga_style = manga_style
        self.gamma = gamma
        self.hq = hq
        self.stretch = stretch
        self.upscale = upscale
        self.webtoon = webtoon
        self.color = color

        self.kcc_bin = self._find_kcc_binary()

    def _find_kcc_binary(self) -> Optional[str]:
        """Find path to kcc-c2e or kindlecomicconverter CLI executable."""
        import os, sys
        kcc_path = shutil.which('kcc-c2e') or shutil.which('kcc') or shutil.which('kindlecomicconverter')
        if kcc_path:
            return kcc_path

        # Check virtual environment bin directory relative to current python executable
        bin_dir = os.path.dirname(sys.executable)
        for name in ['kcc-c2e', 'kcc', 'kindlecomicconverter']:
            candidate = os.path.join(bin_dir, name)
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate

        # Check if runnable via python module
        try:
            res = subprocess.run(
                [sys.executable, '-m', 'kindlecomicconverter.kcc-c2e', '--help'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if res.returncode == 0:
                return f"{sys.executable} -m kindlecomicconverter.kcc-c2e"
        except Exception:
            pass

        return None


    def convert(
        self,
        input_path: Union[str, Path],
        output_dir: Union[str, Path],
        title: Optional[str] = None
    ) -> Path:
        """
        Convert upscaled manga directory or CBZ into Kindle-optimized EPUB/MOBI/AZW3/CBZ.

        Returns:
            Path: Path to created Kindle output file.
        """
        input_path = Path(input_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        book_title = title or input_path.stem

        if self.kcc_bin:
            return self._convert_with_kcc(input_path, output_dir, book_title)
        else:
            print("[Kira Warning] KCC binary (kcc-c2e) not found. Packaging as optimized CBZ fallback...")
            return self._fallback_cbz_convert(input_path, output_dir, book_title)

    def _convert_with_kcc(self, input_path: Path, output_dir: Path, title: str) -> Path:
        """Execute KCC CLI (`kcc-c2e`)."""
        cmd = []
        if ' ' in self.kcc_bin:
            cmd = self.kcc_bin.split(' ')
        else:
            cmd = [self.kcc_bin]

        # KCC CLI Flags
        cmd.extend(['-p', self.profile])
        cmd.extend(['-f', self.output_format])
        cmd.extend(['-o', str(output_dir)])
        cmd.extend(['-t', title])

        if self.manga_style:
            cmd.append('-m')  # Right-to-Left reading order for manga
        if self.hq:
            cmd.append('--hq') # High Quality double-page spread splitting

        if self.stretch:
            cmd.append('-s')
        if self.upscale:
            cmd.append('-u')
        if self.webtoon:
            cmd.append('-w')
        if self.color:
            cmd.append('-c')
        if self.gamma != 1.0:
            cmd.extend(['-g', str(self.gamma)])

        cmd.append(str(input_path))

        print(f"[Kira] Executing KCC adaptation (Profile: {self.profile}, Format: {self.output_format}, Title: {title})...")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res.returncode != 0:
            print(f"[Kira Warning] KCC returned error: {res.stderr.strip()}")
            print("[Kira] Attempting CBZ fallback creation...")
            return self._fallback_cbz_convert(input_path, output_dir, title)

        expected_ext = f".{self.output_format.lower()}"
        target_file = output_dir / f"{title}{expected_ext}"

        if target_file.exists():
            return target_file

        # Check for any created output file matching expected_ext or input_path name
        for cand_name in [input_path.stem, input_path.name, "upscaled"]:
            candidate = output_dir / f"{cand_name}{expected_ext}"
            if candidate.exists():
                if candidate != target_file:
                    shutil.move(candidate, target_file)
                return target_file

        # Check any newly created file with expected extension in output_dir
        for f in output_dir.glob(f"*{expected_ext}"):
            if f.is_file():
                if f != target_file:
                    shutil.move(f, target_file)
                return target_file

        # Fallback check
        matches = [f for f in output_dir.glob(f"{title}*") if f.is_file()]
        if matches:
            return matches[0]

        return target_file



    def _fallback_cbz_convert(self, input_path: Path, output_dir: Path, title: str) -> Path:
        """Fallback when KCC is absent: create clean CBZ archive."""
        cbz_file = output_dir / f"{title}.cbz"
        if input_path.is_dir():
            return create_cbz_archive(input_path, cbz_file)
        else:
            # Copy input archive to output
            out = output_dir / f"{title}{input_path.suffix}"
            shutil.copy2(input_path, out)
            return out
