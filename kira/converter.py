import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

from kira.utils import create_cbz_archive

# Popular Kindle Device Profiles supported by the installed KCC (v11.x)
KINDLE_PROFILES: Dict[str, str] = {
    'KPW5': 'Kindle Paperwhite 5 (11th Gen, 6.8")',
    'KPW34': 'Kindle Paperwhite 3/4 (6")',
    'KPW': 'Kindle Paperwhite 1/2',
    'KO': 'Kindle Oasis (1/2/3)',
    'KS': 'Kindle Scribe (10.2")',
    'K11': 'Kindle Basic (11th Gen 2022)',
    'KV': 'Kindle Voyage',
    'K34': 'Kindle 3/4/5/Touch',
    'K57': 'Kindle 5/7',
    'OTHER': 'Generic E-Reader'
}

# Legacy names accepted for backward compatibility, mapped to real KCC profiles
PROFILE_ALIASES: Dict[str, str] = {
    'KPW3': 'KPW34',
    'K345': 'K34'
}

OUTPUT_FORMATS = ['EPUB', 'CBZ', 'KFX']
LEGACY_FORMATS = {'AZW3': 'EPUB', 'MOBI': 'EPUB'}


class KindleConverter:
    """Wrapper around KCC (Kindle Comic Converter) for adapting upscaled manga to Kindle e-readers."""

    def __init__(
        self,
        profile: str = 'K11',
        output_format: str = 'EPUB',
        manga_style: bool = True,
        gamma: float = 1.0,
        hq: bool = True,
        stretch: bool = False,
        upscale: bool = True,
        webtoon: bool = False,
        color: bool = False,
        cropping: int = 0,
    ):
        profile = profile.upper()
        if profile in PROFILE_ALIASES:
            print(f"[Kira Notice] Profile '{profile}' is deprecated; using '{PROFILE_ALIASES[profile]}' instead.")
            profile = PROFILE_ALIASES[profile]
        if profile not in KINDLE_PROFILES:
            print(f"[Kira Warning] Profile '{profile}' is not supported by KCC. Using 'K11' instead.")
            profile = 'K11'
        self.profile = profile
        fmt = output_format.upper()
        if fmt in LEGACY_FORMATS:
            print(f"[Kira Notice] Format '{fmt}' is deprecated for Kindle (Amazon Send to Kindle requires EPUB). Automatically converting to 'EPUB'.")
            fmt = LEGACY_FORMATS[fmt]

        self.output_format = fmt if fmt in OUTPUT_FORMATS else 'EPUB'

        self.manga_style = manga_style
        self.gamma = gamma
        self.hq = hq
        self.stretch = stretch
        self.upscale = upscale
        self.webtoon = webtoon
        self.color = color
        self.cropping = cropping
        self.last_fallback = False

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


    def _validate_profile_against_kcc(self) -> None:
        """Validate profile against the installed KCC, raising a clear error if unsupported."""
        try:
            from kindlecomicconverter.image import ProfileData
            supported = set(ProfileData.Profiles.keys())
        except Exception:
            return
        if self.profile not in supported:
            raise ValueError(
                f"Profile '{self.profile}' is not supported by the installed KCC. "
                f"Available profiles: {', '.join(sorted(supported))}"
            )

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
        self.last_fallback = False
        input_path = Path(input_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        book_title = title or input_path.stem

        if self.output_format == 'CBZ':
            print(f"[Kira] Packaging CBZ archive for '{book_title}'...")
            self.last_fallback = True
            return self._fallback_cbz_convert(input_path, output_dir, book_title)

        if self.kcc_bin:
            self._validate_profile_against_kcc()
            return self._convert_with_kcc(input_path, output_dir, book_title)
        else:
            print("[Kira Warning] KCC binary (kcc-c2e) not found. Packaging as optimized CBZ fallback...")
            self.last_fallback = True
            return self._fallback_cbz_convert(input_path, output_dir, book_title)

    def _convert_with_kcc(self, input_path: Path, output_dir: Path, title: str) -> Path:
        """Execute KCC CLI (`kcc-c2e`)."""
        cmd = []
        if ' ' in self.kcc_bin:
            cmd = self.kcc_bin.split(' ')
        else:
            cmd = [self.kcc_bin]

        # KCC CLI Flags
        kcc_format = self.output_format.upper()
        cmd.extend(['-p', self.profile])
        cmd.extend(['-f', kcc_format])
        cmd.extend(['-o', str(output_dir)])
        cmd.extend(['-t', title])
        cmd.extend(['--metadatatitle', '2'])
        cmd.extend(['--keepcomicinfo', '1'])

        # Cropping mode (0=disabled default preserves original page art)
        cmd.extend(['-c', str(self.cropping)])

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
            cmd.append('--forcecolor')
        if self.gamma != 1.0:
            cmd.extend(['-g', str(self.gamma)])

        cmd.append(str(input_path))

        print(f"[Kira] Executing KCC adaptation (Profile: {self.profile}, Format: {self.output_format}, Title: {title})...")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            print(f"[Kira Warning] KCC returned error: {err_msg}")
            print("[Kira] Attempting CBZ fallback creation...")
            self.last_fallback = True
            return self._fallback_cbz_convert(input_path, output_dir, title)

        expected_ext = f".{self.output_format.lower()}"
        target_file = output_dir / f"{title}{expected_ext}"

        if target_file.exists():
            return target_file

        # Check for generated files (.azw3, .mobi, .epub, .cbz)
        for ext in [expected_ext, '.mobi', '.azw3', '.epub', '.kepub.epub', '.cbz']:
            for cand_name in [title, input_path.stem, input_path.name, "upscaled"]:
                cand = output_dir / f"{cand_name}{ext}"
                if cand.exists():
                    desired_file = output_dir / f"{title}{cand.suffix}"
                    if cand != desired_file:
                        shutil.move(cand, desired_file)
                        return desired_file
                    return cand

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
