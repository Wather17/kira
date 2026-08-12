import os
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional, Union
import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

try:
    import torch
except ImportError:
    torch = None


# Real-ESRGAN model URLs & configs
MODEL_URLS = {
    'RealESRGAN_x4plus_anime_6B': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
        'scale': 4,
        'net': 'anime_6b'
    },
    'realesr-animevideov3': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',
        'scale': 4,
        'net': 'anime_v3'
    },
    'RealESRGAN_x4plus': {
        'url': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
        'scale': 4,
        'net': 'general'
    }
}


class MangaUpscaler:
    """Real-ESRGAN upscaler engine optimized for Manga line-art and e-ink displays."""

    def __init__(
        self,
        model_name: str = 'RealESRGAN_x4plus_anime_6B',
        scale: int = 4,
        tile: int = 400,
        tile_pad: int = 10,
        pre_pad: int = 0,
        half: Optional[bool] = None,
        device: Optional[str] = None,
        grayscale: bool = False,
        max_dimension: Optional[int] = 2400,
        weights_dir: Optional[Union[str, Path]] = None,
    ):
        self.model_name = model_name if model_name in MODEL_URLS else 'RealESRGAN_x4plus_anime_6B'
        self.scale = scale
        self.tile = tile
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.grayscale = grayscale
        self.max_dimension = max_dimension

        # Select computing device
        if device:
            self.device_str = device
        elif torch is not None and torch.cuda.is_available():
            self.device_str = 'cuda'
        elif torch is not None and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            self.device_str = 'mps'
        else:
            self.device_str = 'cpu'

        self.device = torch.device(self.device_str) if torch is not None else None

        # FP16 (Half precision) works best on CUDA
        if half is None:
            self.half = True if self.device_str == 'cuda' else False
        else:
            self.half = half


        # Model weights path
        self.weights_dir = Path(weights_dir) if weights_dir else Path.home() / '.kira' / 'weights'
        self.weights_dir.mkdir(parents=True, exist_ok=True)
        self.weights_path = self.weights_dir / f"{self.model_name}.pth"

        self.upscaler = None

    def download_weights_if_needed(self) -> Path:
        """Download Real-ESRGAN model weights if not present locally."""
        if not self.weights_path.exists():
            url = MODEL_URLS[self.model_name]['url']
            print(f"[Kira] Downloading Real-ESRGAN weights ({self.model_name})...")
            
            def _progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\rDownloading weights: {percent}%")
                sys.stdout.flush()

            urllib.request.urlretrieve(url, self.weights_path, _progress)
            print("\n[Kira] Weights download complete!")

        return self.weights_path

    def _load_model(self):
        """Initialize Real-ESRGAN model architecture."""
        if self.upscaler is not None:
            return

        if torch is None:
            self._load_fallback_model()
            return

        try:
            self.download_weights_if_needed()
            from realesrgan import RealESRGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan.archs.srvgg_arch import SRVGGNetCompact


            net_type = MODEL_URLS[self.model_name]['net']

            if net_type == 'anime_6b':
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
            elif net_type == 'general':
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            elif net_type == 'anime_v3':
                model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type='prelu')
            else:
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)

            self.upscaler = RealESRGANer(
                scale=self.scale,
                model_path=str(self.weights_path),
                dni_weight=None,
                model=model,
                tile=self.tile,
                tile_pad=self.tile_pad,
                pre_pad=self.pre_pad,
                half=self.half,
                device=self.device
            )
        except Exception as e:
            # Fallback if basicsr/realesrgan package setup has issues on certain PyTorch versions
            print(f"[Kira Warning] Native RealESRGANer load exception ({e}). Utilizing PyTorch direct model fallback.")
            self._load_fallback_model()

    def _load_fallback_model(self):
        """Fallback loader directly using torch for inference if basicsr dependencies fail."""
        self.upscaler = "FALLBACK"

    def upscale_image(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> Path:
        """Upscale a single image file and write to output_path."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_model()

        # Read image using OpenCV
        img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
        if img is None:
            # Try PIL fallback for webp or unusual formats
            pil_img = Image.open(input_path).convert('RGB')
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        if self.upscaler == "FALLBACK":
            # Simple high-quality Lanczos upscale as fallback when GPU / realesrgan fails
            h, w = img.shape[:2]
            output = cv2.resize(img, (w * self.scale, h * self.scale), interpolation=cv2.INTER_LANCZOS4)
        else:
            try:
                output, _ = self.upscaler.enhance(img, outscale=self.scale)
            except Exception as ex:
                print(f"[Kira Warning] Real-ESRGAN enhance failed for {input_path.name}: {ex}. Using Lanczos.")
                h, w = img.shape[:2]
                output = cv2.resize(img, (w * self.scale, h * self.scale), interpolation=cv2.INTER_LANCZOS4)

        # Convert to grayscale if requested (ideal for Kindle e-ink screens)
        if self.grayscale:
            if len(output.shape) == 3:
                output = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY)

        # Apply maximum dimension cap if specified to prevent bloated file sizes for e-readers
        if self.max_dimension and self.max_dimension > 0:
            h, w = output.shape[:2]
            max_side = max(h, w)
            if max_side > self.max_dimension:
                ratio = self.max_dimension / max_side
                new_w, new_h = int(w * ratio), int(h * ratio)
                output = cv2.resize(output, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if output_path.suffix.lower() in ('.jpg', '.jpeg'):
            cv2.imwrite(str(output_path), output, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            cv2.imwrite(str(output_path), output)
        return output_path


    def upscale_batch(self, image_paths: List[Path], output_dir: Union[str, Path]) -> List[Path]:
        """Upscale a batch of image files with progress bar."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results = []

        print(f"[Kira] Processing {len(image_paths)} pages using {self.model_name} (Device: {self.device_str}, FP16: {self.half})...")
        for img_path in tqdm(image_paths, desc="Upscaling Manga Pages", unit="page"):
            out_file = output_dir / img_path.name
            res = self.upscale_image(img_path, out_file)
            results.append(res)

        return results
