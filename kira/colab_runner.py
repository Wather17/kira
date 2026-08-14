import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


def is_colab_cli_available() -> bool:
    """Check if the google-colab-cli (`colab`) executable is available in PATH."""
    return shutil.which("colab") is not None


def run_pipeline_on_colab(
    input_path: str,
    output_dir: str,
    gpu: str = "T4",
    model: str = "RealESRGAN_x4plus_anime_6B",
    profile: str = "K11",
    output_format: str = "AZW3",
    session_name: str = "kira-remote",

    auto_stop: bool = True
) -> bool:
    """
    Provision a remote Google Colab GPU instance, execute the Kira pipeline,
    and release the GPU compute upon completion.
    """
    colab_bin = shutil.which("colab") or "/home/henrique/.local/bin/colab"
    if not os.path.exists(colab_bin) and not is_colab_cli_available():
        console.print("[bold red]Error:[/bold red] Google Colab CLI (`colab`) is not installed.")
        console.print("Run `pip install google-colab-cli` or check PATH.")
        return False

    console.print(f"[bold cyan][Kira Remote][/bold cyan] Initializing Colab GPU Session: [yellow]{session_name}[/yellow] (GPU: [green]{gpu}[/green])...")

    # Step 1: Provision / Connect GPU session
    cmd_new = [colab_bin, "new", "-s", session_name, "--gpu", gpu]
    try:
        res_new = subprocess.run(cmd_new, capture_output=True, text=True)
        if res_new.returncode != 0:
            console.print(f"[bold yellow][Kira Remote Notice][/bold yellow] Session setup response: {res_new.stdout.strip() or res_new.stderr.strip()}")
    except Exception as e:
        console.print(f"[bold red]Failed to launch Colab session:[/bold red] {e}")
        return False

    try:
        # Step 2: Mount Google Drive remotely
        console.print("[bold cyan][Kira Remote][/bold cyan] Mounting Google Drive on remote VM...")
        cmd_mount = [colab_bin, "drivemount", "-s", session_name]
        subprocess.run(cmd_mount, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Step 3: Run pipeline remotely on GPU VM
        console.print(f"[bold cyan][Kira Remote][/bold cyan] Executing Kira Pipeline for '{input_path}' -> '{output_dir}'...")

        remote_script = (
            f"import os, sys; "
            f"os.system('pip install -q git+https://github.com/Wather17/kira.git'); "
            f"os.system('kira process -i \"/content/drive/MyDrive/{input_path}\" "
            f"-o \"/content/drive/MyDrive/{output_dir}\" -m \"{model}\" -p \"{profile}\" -f \"{output_format}\"');"
        )

        cmd_exec = [colab_bin, "exec", "-s", session_name, remote_script]
        proc = subprocess.Popen(cmd_exec, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                print(line, end="")
        proc.wait()

        if proc.returncode == 0:
            console.print(f"[bold green]✓ Kira Remote processing complete for '{session_name}'![/bold green]")
            return True
        else:
            console.print(f"[bold red]✗ Remote processing exited with code {proc.returncode}[/bold red]")
            return False

    finally:
        if auto_stop:
            console.print(f"[bold cyan][Kira Remote][/bold cyan] Stopping GPU session '{session_name}' to release compute...")
            cmd_stop = [colab_bin, "stop", "-s", session_name]
            subprocess.run(cmd_stop, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
