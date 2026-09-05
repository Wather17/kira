import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from kira.pipeline import MangaPipeline
from kira.utils import create_cbz_archive


def _make_cbz(tmp_path: Path, title: str, n_pages: int) -> Path:
    manga_src = tmp_path / f"{title}_pages"
    manga_src.mkdir()
    for i in range(1, n_pages + 1):
        img = Image.new('RGB', (200, 300), color='white')
        img.save(manga_src / f"page_{i:02d}.jpg")
    cbz_input = tmp_path / f"{title}.cbz"
    create_cbz_archive(manga_src, cbz_input)
    return cbz_input


def test_manga_pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_input = _make_cbz(tmp_path, "OnePiece_Ch01", 2)

        out_dir = tmp_path / "output_drive"

        # Initialize pipeline (uses fallback upscaling / convert if torch/realesrgan weights not downloaded in test)
        pipeline = MangaPipeline(
            model_name="RealESRGAN_x4plus_anime_6B",
            scale=4,
            tile=400,
            device="cpu",
            kindle_profile="KPW5",
            output_format="CBZ"
        )

        stats = pipeline.process_item(cbz_input, out_dir)
        assert stats['title'] == "OnePiece_Ch01"
        assert stats['pages'] == 2
        assert Path(stats['output']).exists()
        assert stats['status'] == 'fallback'


def test_manga_pipeline_concurrent_workers():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_input = _make_cbz(tmp_path, "Bleach_Ch01", 4)

        out_dir = tmp_path / "output_drive"

        # Initialize pipeline with 2 concurrent workers
        pipeline = MangaPipeline(
            model_name="RealESRGAN_x4plus_anime_6B",
            scale=4,
            tile=400,
            device="cpu",
            kindle_profile="KPW5",
            output_format="CBZ",
            workers=2
        )

        stats = pipeline.process_item(cbz_input, out_dir)
        assert stats['title'] == "Bleach_Ch01"
        assert stats['pages'] == 4
        assert Path(stats['output']).exists()


def test_pipeline_work_dir_uses_safe_temp_when_no_temp_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_input = _make_cbz(tmp_path, "Naruto_Ch01", 1)
        out_dir = tmp_path / "output_colab"
        safe_dir = tmp_path / "safe_kira_temp"

        with patch("kira.pipeline.get_safe_temp_dir", return_value=safe_dir) as mock_safe:
            pipeline = MangaPipeline(
                model_name="RealESRGAN_x4plus_anime_6B",
                scale=4,
                tile=400,
                device="cpu",
                kindle_profile="KPW5",
                output_format="CBZ"
            )
            stats = pipeline.process_item(cbz_input, out_dir)
        assert stats['title'] == "Naruto_Ch01"
        mock_safe.assert_called_once_with("work")
        assert Path(stats['output']).exists()


def test_pipeline_work_dir_respects_explicit_temp_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cbz_input = _make_cbz(tmp_path, "DeathNote_Ch01", 1)
        out_dir = tmp_path / "output_explicit"
        explicit_temp = tmp_path / "my_temp_dir"

        pipeline = MangaPipeline(
            model_name="RealESRGAN_x4plus_anime_6B",
            scale=4,
            tile=400,
            device="cpu",
            kindle_profile="KPW5",
            output_format="CBZ"
        )
        stats = pipeline.process_item(cbz_input, out_dir, temp_dir=explicit_temp)
        assert stats['title'] == "DeathNote_Ch01"
        assert Path(stats['output']).exists()


def test_pipeline_keep_extracted_isolates_consecutive_items():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        first = _make_cbz(tmp_path, "First", 1)
        second = _make_cbz(tmp_path, "Second", 3)
        work_base = tmp_path / "preserved_work"
        out_dir = tmp_path / "output"

        pipeline = MangaPipeline(
            device="cpu",
            output_format="CBZ",
            keep_extracted=True,
        )
        converted_inputs = []

        def fake_upscale(images, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            result = []
            for image in images:
                target = output_dir / image.name
                shutil.copy2(image, target)
                result.append(target)
            return result

        def fake_convert(input_path, output_dir, title):
            converted_inputs.append(sorted(path.name for path in Path(input_path).iterdir()))
            output = Path(output_dir) / f"{title}.cbz"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"converted")
            return output

        pipeline.upscaler.upscale_batch = fake_upscale
        pipeline.converter.convert = fake_convert

        pipeline.process_item(first, out_dir, temp_dir=work_base)
        pipeline.process_item(second, out_dir, temp_dir=work_base)

        assert len(converted_inputs) == 2
        assert len(converted_inputs[0]) == 1
        assert len(converted_inputs[1]) == 3
        assert len(list(work_base.iterdir())) == 2
