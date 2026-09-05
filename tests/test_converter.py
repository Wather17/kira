import tempfile
from pathlib import Path
from PIL import Image
import pytest
from kira.converter import KINDLE_PROFILES, KindleConverter


def test_kindle_converter_fallback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "upscaled_manga"
        manga_dir.mkdir()

        img = Image.new('RGB', (100, 100), color='white')
        img.save(manga_dir / "0001.jpg")

        converter = KindleConverter(profile='KPW5', output_format='CBZ')
        out_dir = tmp_path / "kindle_out"
        res_file = converter.convert(manga_dir, out_dir, title="TestManga")

        assert res_file.exists()
        assert res_file.suffix.lower() == ".cbz"


def test_kindle_converter_defaults_and_legacy_mapping():
    # Default format is EPUB
    conv_default = KindleConverter()
    assert conv_default.output_format == "EPUB"
    assert conv_default.cropping == 0

    # AZW3 maps to EPUB
    conv_azw3 = KindleConverter(output_format="AZW3")
    assert conv_azw3.output_format == "EPUB"

    # MOBI maps to EPUB
    conv_mobi = KindleConverter(output_format="MOBI")
    assert conv_mobi.output_format == "EPUB"


def test_converter_sends_cropping_0_by_default(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        import subprocess as sp
        class FakeComp:
            def __init__(self):
                self.returncode = 0
                self.stdout = ""
                self.stderr = ""
        return FakeComp()

    monkeypatch.setattr("kira.converter.subprocess.run", fake_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        converter = KindleConverter(profile='K11', output_format='EPUB')
        converter.convert(manga_dir, tmp_path / "out", title="TestManga")
        assert '-c' in captured['cmd']
        assert '0' in captured['cmd']
        idx = captured['cmd'].index('-c')
        assert captured['cmd'][idx + 1] == '0'


def test_converter_sends_cropping_2_when_requested(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        class FakeComp:
            def __init__(self):
                self.returncode = 0
                self.stdout = ""
                self.stderr = ""
        return FakeComp()

    monkeypatch.setattr("kira.converter.subprocess.run", fake_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        converter = KindleConverter(profile='K11', output_format='EPUB', cropping=2)
        converter.convert(manga_dir, tmp_path / "out", title="TestManga")
        idx = captured['cmd'].index('-c')
        assert captured['cmd'][idx + 1] == '2'


def test_converter_cropping_independent_of_profile():
    for profile in ('K11', 'KPW5'):
        converter = KindleConverter(profile=profile, cropping=0)
        assert converter.cropping == 0


def test_converter_color_uses_forcecolor(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        class FakeComp:
            def __init__(self):
                self.returncode = 0
                self.stdout = ""
                self.stderr = ""
        return FakeComp()

    monkeypatch.setattr("kira.converter.subprocess.run", fake_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        converter = KindleConverter(color=True)
        converter.convert(manga_dir, tmp_path / "out", title="TestManga")

        assert '--forcecolor' in captured['cmd']
        # No bare '-c' (without integer value) may appear: every '-c' must carry a value
        idx = 0
        while idx < len(captured['cmd']):
            if captured['cmd'][idx] == '-c':
                assert idx + 1 < len(captured['cmd'])
                assert captured['cmd'][idx + 1] in ('0', '1', '2')
                idx += 2
            else:
                idx += 1


def test_converter_color_false_adds_no_forcecolor(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        class FakeComp:
            def __init__(self):
                self.returncode = 0
                self.stdout = ""
                self.stderr = ""
        return FakeComp()

    monkeypatch.setattr("kira.converter.subprocess.run", fake_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        converter = KindleConverter(color=False)
        converter.convert(manga_dir, tmp_path / "out", title="TestManga")

        assert '--forcecolor' not in captured['cmd']


def test_converter_profiles_match_kcc(monkeypatch):
    profile_data = pytest.importorskip("kindlecomicconverter.image")
    ProfileData = profile_data.ProfileData
    kcc_profiles = set(ProfileData.Profiles.keys())
    assert set(KINDLE_PROFILES.keys()) - kcc_profiles == set()


def test_converter_profile_aliases_resolve():
    conv = KindleConverter(profile='KPW3')
    assert conv.profile == 'KPW34'
    conv2 = KindleConverter(profile='K345')
    assert conv2.profile == 'K34'


def test_converter_unknown_profile_falls_back_to_k11(monkeypatch):
    converter = KindleConverter(profile='BOGUS')
    assert converter.profile == 'K11'


def test_converter_invalid_profile_raises_clear_error(monkeypatch):
    converter = KindleConverter(profile='K11')

    def fake_validate():
        raise ValueError("Profile 'K11' is not supported by the installed KCC. Available profiles: K1, K2, K11, ...")
    monkeypatch.setattr(converter, "_validate_profile_against_kcc", fake_validate)
    converter.kcc_bin = "/usr/bin/fake-kcc"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        try:
            converter.convert(manga_dir, tmp_path / "out", title="TestManga")
            assert False, "expected ValueError"
        except ValueError as e:
            assert "not supported by the installed KCC" in str(e)


def test_converter_fallback_sets_last_fallback_flag():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "upscaled_manga"
        manga_dir.mkdir()
        img = Image.new('RGB', (100, 100), color='white')
        img.save(manga_dir / "0001.jpg")

        converter = KindleConverter(profile='KPW5', output_format='CBZ')
        out_dir = tmp_path / "kindle_out"
        res_file = converter.convert(manga_dir, out_dir, title="TestManga")

        assert res_file.exists()
        assert converter.last_fallback is True


def test_converter_kcc_success_does_not_flag_fallback(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        class FakeComp:
            def __init__(self):
                self.returncode = 0
                self.stdout = ""
                self.stderr = ""
        return FakeComp()

    monkeypatch.setattr("kira.converter.subprocess.run", fake_run)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manga_dir = tmp_path / "manga"
        manga_dir.mkdir()
        converter = KindleConverter(profile='K11', output_format='KFX')
        converter.convert(manga_dir, tmp_path / "out", title="TestManga")
        assert converter.last_fallback is False
