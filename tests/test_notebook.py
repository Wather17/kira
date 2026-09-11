import json
from pathlib import Path


NOTEBOOK_PATH = Path(__file__).parents[1] / "Kira_Manga_Pipeline.ipynb"
CONFIG_TITLE = "#@title ⚙️ Configurações do Pipeline do Kira"
BOOTSTRAP_MARKERS = ("apt-get", "KIRA_ROOT", "pip", "git")


def _config_cells():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code" and CONFIG_TITLE in "".join(cell.get("source", []))
    ]


def _bootstrap_cells():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = []
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if cell.get("cell_type") == "code" and all(marker in source for marker in BOOTSTRAP_MARKERS):
            cells.append(source)
    return cells


def test_notebook_has_one_canonical_pipeline_configuration():
    config_cells = _config_cells()

    assert len(config_cells) == 1
    source = config_cells[0]
    assert source.count("process_directory(") == 1
    for parameter in (
        "Manga_Input_Folder",
        "Kindle_Output_Folder",
        "RealESRGAN_Model",
        "GPU_Tile_Size",
        "Concurrent_Workers",
        "Grayscale_EInk",
        "Max_Dimension_Px",
        "Kindle_Device",
        "Output_Format",
        "Cropping_Mode",
        "Gamma_Correction",
        "Keep_Upscaled_CBZ",
    ):
        assert parameter in source


def test_notebook_configuration_matches_cli_choices():
    source = _config_cells()[0]

    assert 'Kindle_Device = "K11"' in source
    assert '"KPW34"' in source
    assert '"KPW3"' in source
    assert 'Output_Format = "EPUB" #@param ["EPUB", "CBZ", "KFX"]' in source
    assert 'Cropping_Mode = 0 #@param [0, 1, 2]' in source
    assert "cropping=Cropping_Mode" in source
    assert "AZW3" in source and "MOBI" in source


def test_notebook_has_one_fail_fast_bootstrap_with_validation():
    bootstrap_cells = _bootstrap_cells()

    assert len(bootstrap_cells) == 1
    source = bootstrap_cells[0]
    assert "subprocess.run" in source
    assert "check=True" in source
    assert "pip\", \"check" in source
    assert "kira.pipeline" in source
    assert "kcc-c2e" in source
    assert "|| true" not in source
