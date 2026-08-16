import os
import sys
from typing import Optional
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kira.pipeline import MangaPipeline
from kira.converter import KINDLE_PROFILES, KindleConverter
from kira.upscaler import MODEL_URLS, MangaUpscaler
from kira.utils import is_colab, resolve_google_drive_path

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="kira")
def cli():
    """Kira - Manga Upscaling & Kindle Adaptation Pipeline."""
    pass


@cli.command(name="process")
@click.option("-i", "--input", "input_path", required=True, type=str, help="Input CBZ/ZIP file or folder containing manga archives.")
@click.option("-o", "--output", "output_dir", required=True, type=str, help="Output directory for processed Kindle files.")
@click.option("-m", "--model", default="RealESRGAN_x4plus_anime_6B", type=click.Choice(list(MODEL_URLS.keys())), help="Real-ESRGAN model to use.")
@click.option("-p", "--profile", default="K11", type=click.Choice(list(KINDLE_PROFILES.keys())), help="Target Kindle model profile.")

@click.option("-f", "--format", "output_format", default="EPUB", type=click.Choice(["EPUB", "CBZ", "KFX", "AZW3", "MOBI"]), help="Output format (EPUB recommended for Send to Kindle).")

@click.option("--gamma", default=1.0, type=float, help="Gamma correction factor for e-ink contrast.")
@click.option("--grayscale/--color", default=False, help="Convert images to grayscale mode for e-ink.")
@click.option("--tile", default=400, type=int, help="Tile size for Real-ESRGAN GPU upscaling (prevents OOM).")
@click.option("--device", default=None, type=str, help="Device to run upscaling on (cuda, cpu, mps).")
@click.option("--max-dim", default=2400, type=int, help="Maximum image dimension limit (pixels).")
@click.option("--keep-cbz/--no-cbz", default=True, help="Save upscaled CBZ archive alongside Kindle file.")
@click.option("-w", "--workers", default=1, type=int, help="Number of concurrent worker threads for page upscaling (recommended 2 on GPUs >= 8GB VRAM).")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Show verbose output (including Real-ESRGAN tile logs).")
def process(
    input_path: str,
    output_dir: str,
    model: str,
    profile: str,
    output_format: str,
    gamma: float,
    grayscale: bool,
    tile: int,
    device: str,
    max_dim: int,
    keep_cbz: bool,
    workers: int,
    verbose: bool
):
    """Run full pipeline: extract -> Real-ESRGAN upscale -> Kindle adaptation (KCC)."""
    console.print(Panel.fit("[bold magenta]Kira Manga Processing Pipeline[/bold magenta]", border_style="cyan"))

    inp = resolve_google_drive_path(input_path)
    out = resolve_google_drive_path(output_dir)

    pipeline = MangaPipeline(
        model_name=model,
        tile=tile,
        device=device,
        grayscale=grayscale,
        max_dimension=max_dim,
        kindle_profile=profile,
        output_format=output_format,
        gamma=gamma,
        keep_upscaled_cbz=keep_cbz,
        verbose=verbose,
        workers=workers
    )

    if inp.is_file():
        stats = pipeline.process_item(inp, out)
        _print_summary([stats])
    elif inp.is_dir():
        from kira.utils import get_image_files
        direct_images = get_image_files(inp, recursive=False)
        if direct_images:
            # Single manga folder containing images directly
            stats = pipeline.process_item(inp, out)
            _print_summary([stats])
        else:
            # Directory containing subdirectories or archives
            results = pipeline.process_directory(inp, out)
            _print_summary(results)
    else:
        console.print(f"[bold red]Error:[/bold red] Input path '{input_path}' not found.")



@cli.command(name="info")
def info():
    """Show system environment status, GPU details, and dependency status."""
    import shutil


    table = Table(title="Kira Environment Status", border_style="cyan")
    table.add_column("Component", style="bold yellow")
    table.add_column("Status / Details", style="green")


    # Colab check
    table.add_row("Environment", "Google Colab" if is_colab() else "Local System")

    # Python version
    table.add_row("Python Version", f"{sys.version.split()[0]}")

    # PyTorch & GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            gpu_info = f"CUDA Available: {gpu_name} ({vram_gb:.2f} GB VRAM)"
        else:
            gpu_info = "CPU Only (PyTorch installed, no CUDA GPU detected)"
    except ImportError:
        gpu_info = "Not installed (PyTorch is optional for CPU fallback)"

    table.add_row("PyTorch GPU", gpu_info)

    # Real-ESRGAN check
    try:
        import realesrgan
        table.add_row("Real-ESRGAN", "Installed (PyPI package)")
    except ImportError:
        table.add_row("Real-ESRGAN", "PyTorch Fallback mode (realesrgan package not installed)")

    # KCC Binary check
    kcc_converter = KindleConverter()
    if kcc_converter.kcc_bin:
        table.add_row("KCC Converter", f"Found ({kcc_converter.kcc_bin})")
    else:
        table.add_row("KCC Converter", "Not found (CBZ Fallback mode will be used)")

    # 7z check
    seven_z = shutil.which('7z') or shutil.which('unrar')
    table.add_row("RAR Extractor (7z/unrar)", f"Found ({seven_z})" if seven_z else "Not found")

    console.print(table)


@cli.command(name="merge-volumes")
@click.option("-i", "--input", "input_dir", required=True, type=str, help="Input directory containing chapter CBZ files or folders.")
@click.option("-o", "--output", "output_dir", required=True, type=str, help="Output directory to save merged Volume CBZ files.")
@click.option("-t", "--title", default=None, type=str, help="Manga title (optional - auto-detected if not provided).")
@click.option("-m", "--mapping", default=None, type=str, help="Path to custom YAML/JSON chapter mapping file.")
def merge_volumes(input_dir: str, output_dir: str, title: Optional[str], mapping: Optional[str]):

    """Merge individual chapter CBZ files or folders into official Volume archives."""
    from kira.merger import VolumeMerger
    console.print(Panel.fit("[bold green]Kira Manga Volume Merger[/bold green]", border_style="green"))

    inp = resolve_google_drive_path(input_dir)
    out = resolve_google_drive_path(output_dir)

    merger = VolumeMerger(manga_title=title)
    merged_files = merger.merge_all_volumes(inp, out, mapping=mapping)

    console.print(f"\n[bold green]Successfully created {len(merged_files)} Volume CBZ files in {out}[/bold green]")


@cli.command(name="colab-run")
@click.option("-i", "--input", "input_path", required=True, type=str, help="Input folder/file in Google Drive (e.g. Manga_Inputs).")
@click.option("-o", "--output", "output_dir", required=True, type=str, help="Output folder in Google Drive (e.g. Kindle_Outputs).")
@click.option("--gpu", default="T4", type=click.Choice(["T4", "L4", "A100"]), help="Google Colab GPU accelerator type.")
@click.option("-m", "--model", default="RealESRGAN_x4plus_anime_6B", type=click.Choice(list(MODEL_URLS.keys())), help="Real-ESRGAN model to use.")
@click.option("-p", "--profile", default="K11", type=click.Choice(list(KINDLE_PROFILES.keys())), help="Target Kindle profile.")

@click.option("-f", "--format", "output_format", default="EPUB", type=click.Choice(["EPUB", "CBZ", "KFX", "AZW3", "MOBI"]), help="Output format.")
@click.option("--tile", default=600, type=int, help="Tile size for GPU upscaling (default: 600 for Colab GPU).")
@click.option("-w", "--workers", default=2, type=int, help="Number of concurrent worker threads (default: 2 for Colab GPU).")
@click.option("--session-name", default="kira-remote", type=str, help="Colab session name.")
@click.option("--auto-stop/--no-stop", default=True, help="Automatically release GPU session after processing finishes.")
def colab_run(
    input_path: str,
    output_dir: str,
    gpu: str,
    model: str,
    profile: str,
    output_format: str,
    tile: int,
    workers: int,
    session_name: str,
    auto_stop: bool
):
    """Provision a remote Google Colab GPU instance and run the pipeline headlessly."""
    from kira.colab_runner import run_pipeline_on_colab
    success = run_pipeline_on_colab(
        input_path=input_path,
        output_dir=output_dir,
        gpu=gpu,
        model=model,
        profile=profile,
        output_format=output_format,
        tile=tile,
        workers=workers,
        session_name=session_name,
        auto_stop=auto_stop
    )
    if not success:
        sys.exit(1)


@cli.command(name="colab-setup")

def colab_setup():
    """Install required dependencies inside a Google Colab notebook environment."""
    console.print("[bold cyan]Installing Kira dependencies for Google Colab...[/bold cyan]")
    os.system("pip install -q torch torchvision realesrgan natsort tqdm Pillow opencv-python rich click PyYAML rarfile")
    os.system("apt-get update -qq && apt-get install -y -qq p7zip-full unrar python3-kindlecomicconverter kcc")
    console.print("[bold green]Colab setup complete![/bold green]")



def _print_summary(stats_list):
    if not stats_list:
        return
    table = Table(title="Kira Processing Summary", border_style="magenta")
    table.add_column("Title", style="bold white")
    table.add_column("Pages", style="cyan", justify="right")
    table.add_column("Time (s)", style="yellow", justify="right")
    table.add_column("Size (MB)", style="green", justify="right")
    table.add_column("Output File", style="dim")

    for item in stats_list:
        table.add_row(
            str(item['title']),
            str(item['pages']),
            f"{item['time_seconds']:.1f}",
            f"{item['size_mb']:.2f}",
            Path(str(item['output'])).name
        )
    console.print("\n")
    console.print(table)


if __name__ == "__main__":
    cli()
