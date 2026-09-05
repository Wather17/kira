import subprocess
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner
from kira.cli import cli


def _kcc_version_stdout(version="11.0.1"):
    return f"comic2ebook v{version} - Written by Ciro Mattia Gonano and Pawel Jastrzebski." + "\n"


def test_colab_setup_installs_kcc_via_pip_not_apt():
    runner = CliRunner()
    captured_cmds = []

    def fake_system(cmd):
        captured_cmds.append(cmd)
        return 0

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.stdout = _kcc_version_stdout("11.0.1")
        mock.stderr = ""
        return mock

    with patch("os.system", side_effect=fake_system), \
         patch("shutil.which", return_value="/usr/local/bin/kcc-c2e"), \
         patch("subprocess.run", side_effect=fake_run):
        result = runner.invoke(cli, ["colab-setup"], standalone_mode=False)

    assert result.exit_code == 0
    pip_cmd = [c for c in captured_cmds if c.startswith("pip install")]
    apt_cmd = [c for c in captured_cmds if c.startswith("apt-get")]
    assert pip_cmd and "git+https://github.com/ciromattia/kcc.git" in pip_cmd[0]
    assert apt_cmd and "kindlecomicconverter" not in apt_cmd[0] and " kcc " not in f" {apt_cmd[0]} "


def test_colab_setup_aborts_on_pip_failure():
    runner = CliRunner()

    def fake_system(cmd):
        return 1 if cmd.startswith("pip install") else 0

    with patch("os.system", side_effect=fake_system), \
         patch("shutil.which", return_value="/usr/local/bin/kcc-c2e"):
        result = runner.invoke(cli, ["colab-setup"], standalone_mode=False)

    assert result.exit_code == 1


def test_colab_setup_aborts_when_kcc_missing_after_install():
    runner = CliRunner()

    with patch("os.system", return_value=0), \
         patch("shutil.which", return_value=None):
        result = runner.invoke(cli, ["colab-setup"], standalone_mode=False)

    assert result.exit_code == 1


def test_colab_setup_warns_on_old_kcc_version():
    runner = CliRunner()

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.stdout = _kcc_version_stdout("4.12")
        mock.stderr = ""
        return mock

    with patch("os.system", return_value=0), \
         patch("shutil.which", return_value="/usr/local/bin/kcc-c2e"), \
         patch("subprocess.run", side_effect=fake_run):
        result = runner.invoke(cli, ["colab-setup"], standalone_mode=False)

    assert result.exit_code == 1


def test_colab_setup_success_with_new_kcc():
    runner = CliRunner()

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.stdout = _kcc_version_stdout("11.0.1")
        mock.stderr = ""
        return mock

    with patch("os.system", return_value=0), \
         patch("shutil.which", return_value="/usr/local/bin/kcc-c2e"), \
         patch("subprocess.run", side_effect=fake_run):
        result = runner.invoke(cli, ["colab-setup"], standalone_mode=False)

    assert result.exit_code == 0
