from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import pytest

from kira.cli import cli


@pytest.mark.parametrize("flags,enabled", [
    ([], None),
    (["--canvas"], True),
    (["--no-canvas"], False),
])
def test_process_passes_canvas_mode_and_custom_top_margin(tmp_path, flags, enabled):
    input_file = tmp_path / "manga.cbz"
    input_file.touch()
    with patch("kira.cli.MangaPipeline") as pipeline, patch("kira.cli._print_summary"):
        result = CliRunner().invoke(cli, [
            "process", "-i", str(input_file), "-o", str(tmp_path / "out"),
            "--canvas-top", "4", *flags,
        ])
    assert result.exit_code == 0, result.output
    canvas = pipeline.call_args.kwargs["canvas"]
    assert canvas.enabled is enabled
    assert (canvas.top_margin_pct, canvas.bottom_margin_pct) == (4.0, 2.0)
    assert (canvas.left_margin_pct, canvas.right_margin_pct) == (3.0, 3.0)


def test_process_missing_input_returns_nonzero(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["process", "-i", str(tmp_path / "missing.cbz"), "-o", str(tmp_path / "output")],
    )

    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_process_batch_failure_returns_nonzero_and_names_failed_item(tmp_path: Path):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    output_dir = tmp_path / "outputs"
    fake_pipeline = MagicMock()
    fake_pipeline.process_directory.return_value = []
    fake_pipeline.last_failures = [
        {"item": str(input_dir / "broken.cbz"), "error": "invalid archive"}
    ]

    with patch("kira.cli.MangaPipeline", return_value=fake_pipeline):
        result = CliRunner().invoke(
            cli,
            ["process", "-i", str(input_dir), "-o", str(output_dir)],
        )

    assert result.exit_code != 0
    assert "broken.cbz" in result.output
    assert "1 item(s) failed" in result.output
