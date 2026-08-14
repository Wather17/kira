from unittest.mock import MagicMock, patch
from kira.colab_runner import is_colab_cli_available, run_pipeline_on_colab

def test_is_colab_cli_available():
    with patch("shutil.which", return_value="/usr/bin/colab"):
        assert is_colab_cli_available() is True

    with patch("shutil.which", return_value=None):
        assert is_colab_cli_available() is False


def test_run_pipeline_on_colab_success():
    mock_subprocess_run = MagicMock()
    mock_subprocess_run.returncode = 0
    mock_subprocess_run.stdout = "OK"

    mock_popen = MagicMock()
    mock_popen.stdout.readline.side_effect = ["Starting processing...\n", "Completed!\n", ""]
    mock_popen.returncode = 0

    with patch("shutil.which", return_value="/usr/bin/colab"), \
         patch("os.path.exists", return_value=True), \
         patch("subprocess.run", return_value=mock_subprocess_run), \
         patch("subprocess.Popen", return_value=mock_popen):

        res = run_pipeline_on_colab(
            input_path="Manga_Inputs",
            output_dir="Kindle_Outputs",
            gpu="T4",
            session_name="test-kira-gpu",
            auto_stop=True
        )
        assert res is True
