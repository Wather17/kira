import tempfile
from pathlib import Path
from PIL import Image
from kira.pipeline import MangaPipeline
from kira.utils import create_cbz_archive


def test_manga_pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_src = tmp_path / "manga_pages"
        manga_src.mkdir()

        # Create sample manga pages
        for i in range(1, 3):
            img = Image.new('RGB', (200, 300), color='white')
            img.save(manga_src / f"page_{i:02d}.jpg")

        cbz_input = tmp_path / "OnePiece_Ch01.cbz"
        create_cbz_archive(manga_src, cbz_input)

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
