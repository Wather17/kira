"""Offline structural and visual checks for Kira EPUB output.

The optional browser preview is deliberately reported as approximate: it does
not model Kindle firmware or Amazon's Send to Kindle conversion.
"""

from __future__ import annotations

import hashlib
import json
import math
import posixpath
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageStat

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container",
      "o": "http://www.idpf.org/2007/opf",
      "x": "http://www.w3.org/1999/xhtml"}


class AuditError(ValueError):
    """Invalid or unsupported audit input."""


@dataclass
class PageResult:
    index: int
    source: Optional[str]
    epub_image: str
    source_count: int
    epub_size: tuple[int, int]
    source_size: Optional[tuple[int, int]]
    status: str
    findings: list[str]
    metrics: dict


def _safe_member(path: str) -> str:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(posixpath.normpath(normalized))
    if pure.is_absolute() or pure.parts[0] == "..":
        raise AuditError(f"EPUB contains an unsafe path: {path}")
    return str(pure)


def _read_ordered_images(epub: zipfile.ZipFile) -> tuple[list[str], list[str], dict[str, str]]:
    try:
        container = ET.fromstring(epub.read("META-INF/container.xml"))
        rootfile = container.find(".//c:rootfile", NS)
        if rootfile is None or not rootfile.get("full-path"):
            raise AuditError("EPUB container has no package document")
        opf_path = _safe_member(rootfile.get("full-path", ""))
        package = ET.fromstring(epub.read(opf_path))
    except (KeyError, ET.ParseError) as exc:
        raise AuditError(f"Invalid EPUB package structure: {exc}") from exc

    base = PurePosixPath(opf_path).parent
    manifest: dict[str, str] = {}
    xhtml: dict[str, str] = {}
    for item in package.findall(".//o:manifest/o:item", NS):
        ident, href = item.get("id"), item.get("href")
        if not ident or not href:
            continue
        href_path = _safe_member(unquote(urlsplit(href).path))
        full = _safe_member(str(base / href_path))
        manifest[ident] = full
        if item.get("media-type") == "application/xhtml+xml":
            xhtml[ident] = full

    spine_docs = []
    image_map: dict[str, str] = {}
    for itemref in package.findall(".//o:spine/o:itemref", NS):
        href = xhtml.get(itemref.get("idref", ""))
        if not href:
            continue
        spine_docs.append(href)
        try:
            document = ET.fromstring(epub.read(href))
        except (KeyError, ET.ParseError) as exc:
            raise AuditError(f"Invalid spine XHTML {href}: {exc}") from exc
        for node in document.iter():
            src = node.get("src") or node.get("{http://www.w3.org/1999/xlink}href")
            if node.tag.rsplit("}", 1)[-1].lower() != "img" or not src:
                continue
            image_path = _safe_member(str(PurePosixPath(href).parent / unquote(urlsplit(src).path)))
            if image_path in epub.namelist() and Path(image_path).suffix.lower() in IMAGE_SUFFIXES:
                image_map.setdefault(image_path, href)
    if not spine_docs:
        raise AuditError("EPUB spine contains no readable XHTML pages")
    return spine_docs, list(image_map), image_map


def _images(path: Optional[Path]) -> list[Path]:
    if path is None:
        return []
    path = Path(path)
    if path.is_dir():
        return sorted((p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES), key=lambda p: p.as_posix().casefold())
    if path.suffix.lower() in {".cbz", ".zip"}:
        # Read archives separately in _source_bytes; names here preserve archive order.
        with zipfile.ZipFile(path) as archive:
            return [Path(info.filename) for info in archive.infolist() if not info.is_dir() and Path(info.filename).suffix.lower() in IMAGE_SUFFIXES]
    if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
        return [path]
    raise AuditError(f"Unsupported or missing image source: {path}")


def _source_bytes(path: Path, member: Path) -> bytes:
    if path.is_dir() or (path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES):
        return (path / member).read_bytes() if path.is_dir() else path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        return archive.read(member.as_posix())


def _open_image(data: bytes) -> Image.Image:
    with Image.open(__import__("io").BytesIO(data)) as image:
        return image.convert("RGB")


def _compare(source: Image.Image, target: Image.Image) -> tuple[dict, list[str]]:
    # Aspect-fit into a neutral canvas, so resizing and modest letterboxing are not called cropping.
    canvas = Image.new("RGB", target.size, "white")
    fitted = source.copy()
    fitted.thumbnail(target.size, Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((target.width - fitted.width) // 2, (target.height - fitted.height) // 2))
    # Normalize luminance/contrast lightly, then compare pixels and edge occupancy.
    gray_a = canvas.convert("L")
    gray_b = target.convert("L")
    diff = ImageChops.difference(gray_a, gray_b)
    mae = ImageStat.Stat(diff).mean[0] / 255
    findings = []
    if source.width / source.height > target.width / target.height * 1.2 or source.height / source.width > target.height / target.width * 1.2:
        findings.append("aspect_ratio_changed")
    # Compare content bounding boxes after ignoring near-white paper/background.
    def bbox(image):
        return ImageChops.invert(image.point(lambda p: 255 if p > 245 else 0)).getbbox()
    box_a, box_b = bbox(gray_a), bbox(gray_b)
    lost_edges = []
    if box_a and box_b:
        expected_area = max(1, box_a[2] - box_a[0]) * max(1, box_a[3] - box_a[1])
        actual_area = max(1, box_b[2] - box_b[0]) * max(1, box_b[3] - box_b[1])
        if actual_area < expected_area * 0.65:
            findings.append("content_area_reduced")
        # A source edge margin that disappears in the output is a crop candidate.
        # Flag for review; edge-to-edge artwork can be intentional.
        for side, source_margin, target_margin, extent in (
            ("left", box_a[0] / gray_a.width, box_b[0] / gray_b.width, gray_b.width),
            ("top", box_a[1] / gray_a.height, box_b[1] / gray_b.height, gray_b.height),
            ("right", (gray_a.width - box_a[2]) / gray_a.width, (gray_b.width - box_b[2]) / gray_b.width, gray_b.width),
            ("bottom", (gray_a.height - box_a[3]) / gray_a.height, (gray_b.height - box_b[3]) / gray_b.height, gray_b.height),
        ):
            if source_margin > 0.01 and target_margin < 0.003 and (source_margin - target_margin) > 0.008:
                lost_edges.append(side)
        if lost_edges:
            findings.append("edge_content_may_be_clipped")
    return {"normalized_mae": round(mae, 6), "source_content_bbox": box_a, "epub_content_bbox": box_b, "suspected_clipped_edges": lost_edges}, findings


def _render_preview(epub_path: Path, spine: list[str], image_map: dict[str, str], output: Path, width: int, height: int) -> dict:
    browser = shutil.which("firefox") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if not browser:
        return {"status": "inconclusive", "reason": "No supported headless browser found", "captures": []}
    captures = []
    # Render the actual spine XHTML from an isolated, temporary extraction.
    # This remains an approximation, never a device compatibility verdict.
    try:
        with tempfile.TemporaryDirectory(prefix="kira-audit-") as temp:
            root = Path(temp)
            with zipfile.ZipFile(epub_path) as archive:
                for info in archive.infolist():
                    name = _safe_member(info.filename)
                    if not info.is_dir():
                        target_path = root / name
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_bytes(archive.read(info))
            for idx, doc in enumerate(spine, 1):
                target = output / "previews" / f"page-{idx:04d}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                page = root / doc
                args = [browser, "--headless"]
                if "firefox" in Path(browser).name:
                    args.extend(["--window-size", f"{width},{height}", "--screenshot", str(target), page.as_uri()])
                else:
                    args.extend([f"--window-size={width},{height}", f"--screenshot={target}", page.as_uri()])
                subprocess.run(args, check=True, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if not target.is_file():
                    raise RuntimeError("browser exited without producing a screenshot")
                captures.append(str(target.relative_to(output)))
    except Exception as exc:
        return {"status": "inconclusive", "reason": f"Browser rendering failed: {exc}", "captures": captures}
    try:
        thumbs = []
        for capture in captures:
            with Image.open(output / capture) as image:
                image = image.convert("RGB")
                image.thumbnail((180, 240), Image.Resampling.LANCZOS)
                thumbs.append(image.copy())
        if thumbs:
            columns = min(5, len(thumbs))
            rows = math.ceil(len(thumbs) / columns)
            sheet = Image.new("RGB", (columns * 190, rows * 250), "#dddddd")
            for idx, thumb in enumerate(thumbs):
                x, y = (idx % columns) * 190, (idx // columns) * 250
                sheet.paste(thumb, (x + (180 - thumb.width) // 2, y))
            sheet.save(output / "contact_sheet.png")
    except Exception as exc:
        return {"status": "inconclusive", "reason": f"Contact sheet generation failed: {exc}", "captures": captures}
    return {"status": "approximate", "warning": "Browser rendering is not Kindle firmware or Send to Kindle emulation", "viewport": [width, height], "captures": captures, "contact_sheet": "contact_sheet.png"}


def audit_epub(epub_path: Path, output_dir: Path, source_path: Optional[Path] = None, upscaled_path: Optional[Path] = None, profile: str = "K11", render: bool = True, baseline_path: Optional[Path] = None) -> dict:
    epub_path, output_dir = Path(epub_path), Path(output_dir)
    if profile.upper() != "K11":
        raise AuditError("Only K11 preview dimensions are currently configured")
    if not epub_path.is_file():
        raise AuditError(f"EPUB not found: {epub_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = _images(upscaled_path or source_path)
    if upscaled_path and source_path:
        # Stage linkage is currently sequential; report both stages as explicit inputs.
        original_count = len(_images(source_path))
    else:
        original_count = None
    pages: list[PageResult] = []
    with zipfile.ZipFile(epub_path) as archive:
        bad = archive.testzip()
        if bad:
            raise AuditError(f"EPUB ZIP integrity failed at {bad}")
        spine, image_names, image_map = _read_ordered_images(archive)
        if not image_names:
            raise AuditError("EPUB spine contains no linked page images; refusing to report a CBZ fallback as an audited EPUB")
        source_path_for_bytes = Path(upscaled_path or source_path) if (upscaled_path or source_path) else None
        spread_matches = {}
        if sources and source_path_for_bytes is not None and len(image_names) > 1:
            targets = [_open_image(archive.read(name)) for name in image_names]
            wide_sources = []
            for candidate in sources:
                try:
                    image = _open_image(_source_bytes(source_path_for_bytes, candidate))
                    if image.width / image.height >= 1.35:
                        wide_sources.append((candidate, image))
                except Exception:
                    continue
            for source_name, source_image in wide_sources:
                for idx in range(len(targets) - 1):
                    left, right = targets[idx], targets[idx + 1]
                    height = max(left.height, right.height)
                    left = left.resize((max(1, round(left.width * height / left.height)), height), Image.Resampling.LANCZOS)
                    right = right.resize((max(1, round(right.width * height / right.height)), height), Image.Resampling.LANCZOS)
                    combined = Image.new("RGB", (left.width + right.width, height), "white")
                    combined.paste(left, (0, 0)); combined.paste(right, (left.width, 0))
                    reverse = Image.new("RGB", combined.size, "white")
                    reverse.paste(right, (0, 0)); reverse.paste(left, (right.width, 0))
                    candidates = [_compare(source_image, combined)[0]["normalized_mae"], _compare(source_image, reverse)[0]["normalized_mae"]]
                    score = min(candidates)
                    aspect_delta = abs((combined.width / combined.height) - (source_image.width / source_image.height))
                    if aspect_delta < source_image.width / source_image.height * 0.18 and score < 0.16:
                        spread_matches[idx] = (source_name.as_posix(), source_image.size, score)
                        spread_matches[idx + 1] = (source_name.as_posix(), source_image.size, score)
        for index, name in enumerate(image_names, 1):
            findings, metrics, source_name, source_size, source_count = [], {}, None, None, 0
            try:
                target = _open_image(archive.read(name))
            except Exception as exc:
                pages.append(PageResult(index, None, name, 0, (0, 0), None, "fail", [f"invalid_image: {exc}"], {}))
                continue
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            metrics["sha256"] = digest
            if index - 1 in spread_matches:
                source_name, source_size, score = spread_matches[index - 1]
                source_count = 2
                metrics.update({"normalized_mae": score, "spread_pair": [index - 1, index]})
                findings.append("matched_as_lossless_spread_split")
            elif sources and source_path_for_bytes is not None:
                # Handle correct 1:N spread splits by comparing each target against the best source candidate.
                scored = []
                for candidate in sources:
                    try:
                        img = _open_image(_source_bytes(source_path_for_bytes, candidate))
                        score, flags = _compare(img, target)
                        scored.append((score["normalized_mae"], candidate, img, score, flags))
                    except Exception:
                        continue
                if scored:
                    _, candidate, img, score, flags = min(scored, key=lambda row: row[0])
                    source_name, source_size, source_count = candidate.as_posix(), img.size, 1
                    metrics.update(score)
                    # Only flag dramatic losses; report the metric for human review.
                    if score["normalized_mae"] > 0.45:
                        findings.append("high_visual_difference")
                    findings.extend(flags)
            status = "suspect" if findings else ("pass" if source_path_for_bytes else "not_compared")
            pages.append(PageResult(index, source_name, name, source_count, target.size, source_size, status, sorted(set(findings)), metrics))
    renderer = _render_preview(epub_path, spine, image_map, output_dir, 1072, 1448) if render else {"status": "not_requested", "captures": []}
    report = {"schema_version": 1, "profile": profile.upper(), "epub": str(epub_path.resolve()), "epub_sha256": hashlib.sha256(epub_path.read_bytes()).hexdigest(), "source_count": len(sources), "original_source_count": original_count, "spine_documents": spine, "page_count": len(pages), "pages": [asdict(page) for page in pages], "preview": renderer, "limitations": ["Browser preview is approximate and does not emulate Kindle firmware or Send to Kindle.", "Automatic image correspondence is heuristic; spread splits and uncertain matches must be reviewed."]}
    if baseline_path:
        try:
            baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
            old_pages = baseline.get("pages", [])
            regressions = []
            for idx, page in enumerate(report["pages"]):
                if idx >= len(old_pages):
                    regressions.append({"page": idx + 1, "kind": "page_added"})
                    continue
                before = old_pages[idx]
                old_metric = before.get("metrics", {}).get("normalized_mae")
                new_metric = page.get("metrics", {}).get("normalized_mae")
                if old_metric is not None and new_metric is not None and new_metric - old_metric > 0.08:
                    regressions.append({"page": idx + 1, "kind": "visual_difference_increased", "previous": old_metric, "current": new_metric})
            if len(old_pages) > len(report["pages"]):
                regressions.extend({"page": idx + 1, "kind": "page_removed"} for idx in range(len(report["pages"]), len(old_pages)))
            report["baseline"] = str(Path(baseline_path).resolve())
            report["regressions"] = regressions
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditError(f"Could not read baseline report: {exc}") from exc
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
