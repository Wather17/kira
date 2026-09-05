from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from kira.cli import cli


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
