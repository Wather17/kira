import json
from pathlib import Path


NOTEBOOK_PATH = Path(__file__).parents[1] / "Kira_Manga_Pipeline.ipynb"
CONFIG_TITLE = "#@title ⚙️ Configurações do Pipeline do Kira"


def _config_cells():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code" and CONFIG_TITLE in "".join(cell.get("source", []))
    ]


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
        "Gamma_Correction",
        "Keep_Upscaled_CBZ",
    ):
        assert parameter in source


def test_notebook_configuration_matches_cli_choices():
    source = _config_cells()[0]

    assert 'Kindle_Device = "K11"' in source
    assert '"KPW34"' in source
    assert '"KPW3"' in source
    assert 'Output_Format = "EPUB"' in source
    assert '"AZW3"' in source
    assert '"MOBI"' in source
