import os
import json
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


def _build_remote_script_code(
    input_path: str,
    output_dir: str,
    model: str,
    profile: str,
    output_format: str,
    tile: int,
    workers: int,
) -> str:
    """Build the remote Python script that runs the Kira pipeline via argv (no shell)."""
    return f"""
import os, sys, subprocess
from pathlib import Path

def resolve_remote_path(path_str):
    p = Path(path_str).expanduser()
    colab_drive_root = Path('/content/drive/MyDrive')
    s = str(p)
    if s.startswith('/content/drive/MyDrive'):
        return p
    elif s.startswith('MyDrive/'):
        return colab_drive_root / s[len('MyDrive/'):]
    elif s in ('MyDrive', 'drive/MyDrive'):
        return colab_drive_root
    elif s.startswith('drive/MyDrive/'):
        return colab_drive_root / s[len('drive/MyDrive/'):]
    elif not p.is_absolute():
        if colab_drive_root.exists():
            return colab_drive_root / p
    return p.resolve()

# Mount Google Drive if not already mounted
if not os.path.exists('/content/drive/MyDrive'):
    print('[Remote Colab Worker] Mounting Google Drive...')
    try:
        from google.colab import drive
        drive.mount('/content/drive')
    except Exception as e:
        print(f'[Remote Colab Worker] Note: {{e}}')

print('[Remote Colab Worker] Installing system packages & latest Kira...')
os.system('apt-get update -qq && apt-get install -y -qq p7zip-full unrar > /dev/null 2>&1')
os.system('pip install -q git+https://github.com/Wather17/kira.git')

input_path = {json.dumps(input_path)}
output_dir = {json.dumps(output_dir)}
model = {json.dumps(model)}
profile = {json.dumps(profile)}
output_format = {json.dumps(output_format)}
tile = {json.dumps(tile)}
workers = {json.dumps(workers)}

input_resolved = resolve_remote_path(input_path)
output_resolved = resolve_remote_path(output_dir)

print('[Remote Colab Worker] Running Kira Manga Pipeline (High-Performance GPU mode)...')
print(f"[Remote Colab Worker] Input: {{input_resolved}} -> Output: {{output_resolved}}")
try:
    res = subprocess.run(
        ['kira', 'process',
         '-i', str(input_resolved),
         '-o', str(output_resolved),
         '-m', model,
         '-p', profile,
         '-f', output_format,
         '--tile', str(tile),
         '--workers', str(workers)],
        text=True,
    )
except Exception as e:
    print(f'[Remote Colab Worker] Failed to execute Kira pipeline: {{e}}')
    sys.exit(1)
if res.returncode != 0:
    sys.exit(1)
"""


def run_pipeline_on_colab(
    input_path: str,
    output_dir: str,
    gpu: str = "T4",
    model: str = "RealESRGAN_x4plus_anime_6B",
    profile: str = "K11",
    output_format: str = "AZW3",
    session_name: str = "kira-remote",
    tile: int = 600,
    workers: int = 2,
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

    console.print(f"[bold cyan][Kira Remote][/bold cyan] Initializing Colab GPU Session: [yellow]{session_name}[/yellow] (GPU: [green]{gpu}[/green], Workers: [magenta]{workers}[/magenta], Tile: [cyan]{tile}[/cyan])...")

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
        # Step 2: Run pipeline remotely on GPU VM
        console.print(f"[bold cyan][Kira Remote][/bold cyan] Executing Kira Pipeline for '{input_path}' -> '{output_dir}'...")

        import tempfile
        script_code = _build_remote_script_code(
            input_path=input_path,
            output_dir=output_dir,
            model=model,
            profile=profile,
            output_format=output_format,
            tile=tile,
            workers=workers,
        )

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script_code)
            temp_script_path = f.name

        try:
            cmd_exec = [colab_bin, "exec", "-s", session_name, "-f", temp_script_path, "--timeout", "86400"]
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
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)


    finally:
        if auto_stop:
            console.print(f"[bold cyan][Kira Remote][/bold cyan] Stopping GPU session '{session_name}' to release compute...")
            cmd_stop = [colab_bin, "stop", "-s", session_name]
            subprocess.run(cmd_stop, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
