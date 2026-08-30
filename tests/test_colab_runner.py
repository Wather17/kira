from pathlib import Path
from unittest.mock import MagicMock, patch
from kira.colab_runner import _build_remote_script_code, is_colab_cli_available, run_pipeline_on_colab

def test_is_colab_cli_available():
    with patch("shutil.which", return_value="/usr/bin/colab"):
        assert is_colab_cli_available() is True

    with patch("shutil.which", return_value=None):
        assert is_colab_cli_available() is False


def test_remote_script_uses_argv_not_shell():
    script = _build_remote_script_code(
        input_path="MyDrive/Manga",
        output_dir="Kindle_Out",
        model="RealESRGAN_x4plus_anime_6B",
        profile="K11",
        output_format="EPUB",
        tile=600,
        workers=2,
    )
    assert "subprocess.run(" in script
    assert "['kira', 'process'" in script
    assert "os.system('kira process" not in script
    assert "resolve_remote_path" in script


def test_remote_script_preserves_hostile_paths_literally():
    hostile = 'Manga; rm -rf /; `id` "quoted" \\backslash'
    script = _build_remote_script_code(
        input_path=hostile,
        output_dir="Kindle_Out",
        model="RealESRGAN_x4plus_anime_6B",
        profile="K11",
        output_format="EPUB",
        tile=600,
        workers=2,
    )
    # Paths are embedded as JSON literals: safe Python representation, decoded at runtime
    import json
    assert json.dumps(hostile) in script
    assert "os.system('kira process" not in script
    # The literal value survives an eval cycle as the remote interpreter sees it
    assert eval(json.dumps(hostile)) == hostile


def test_remote_script_resolves_mydrive_variants():
    script = _build_remote_script_code(
        input_path="MyDrive/Manga",
        output_dir="Kindle_Out",
        model="RealESRGAN_x4plus_anime_6B",
        profile="K11",
        output_format="EPUB",
        tile=600,
        workers=2,
    )
    assert "colab_drive_root = Path('/content/drive/MyDrive')" in script
    assert "startswith('MyDrive/')" in script
    assert "startswith('drive/MyDrive/')" in script
    assert "startswith('/content/drive/MyDrive')" in script


def test_run_pipeline_on_colab_uses_home_bin_fallback():
    import subprocess as sp

    mock_subprocess_run = MagicMock()
    mock_subprocess_run.returncode = 0
    mock_subprocess_run.stdout = "OK"

    mock_popen = MagicMock()
    mock_popen.stdout.readline.side_effect = ["Starting processing...\n", "Completed!\n", ""]
    mock_popen.returncode = 0

    captured_cmds = []
    fake_run = MagicMock(return_value=mock_subprocess_run)

    def record_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return fake_run(cmd, **kwargs)

    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=True), \
         patch.object(sp, "run", side_effect=record_run), \
         patch("pathlib.Path.home", return_value=Path("/usr/otheruser")), \
         patch("subprocess.Popen", return_value=mock_popen):

        res = run_pipeline_on_colab(
            input_path="Manga_Inputs",
            output_dir="Kindle_Outputs",
            gpu="T4",
            session_name="test-kira-gpu",
            auto_stop=True
        )
        assert res is True
        new_cmds = [c for c in captured_cmds if "new" in c]
        assert new_cmds[0][0] == str(Path("/usr/otheruser/.local/bin/colab"))
        assert "/home/henrique" not in str(new_cmds[0][0])

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
