"""Fixed-canvas normalization for Kindle EPUB output."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
import posixpath
from pathlib import Path
import tempfile
from statistics import median
from typing import Dict, Iterable, Optional, Tuple
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image


XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"

ET.register_namespace("", XHTML_NS)
ET.register_namespace("epub", EPUB_NS)
ET.register_namespace("opf", OPF_NS)

K11_LOGICAL_SIZE = (1072, 1448)
HQ_SCALE = 1.5


class CanvasError(ValueError):
    """Raised when a canvas cannot be applied safely to an EPUB."""


@dataclass(frozen=True)
class CanvasConfig:
    """Canvas margins in percent. The converter resolves None as automatic."""

    enabled: Optional[bool] = False
    top_margin_pct: float = 2.0
    bottom_margin_pct: float = 2.0
    left_margin_pct: float = 3.0
    right_margin_pct: float = 3.0

    def __post_init__(self) -> None:
        margins = {
            "top_margin_pct": self.top_margin_pct,
            "bottom_margin_pct": self.bottom_margin_pct,
            "left_margin_pct": self.left_margin_pct,
            "right_margin_pct": self.right_margin_pct,
        }
        for name, value in margins.items():
            if not 0 <= value < 100:
                raise CanvasError(f"{name} must be between 0 and 99.99")
        if self.top_margin_pct + self.bottom_margin_pct >= 100:
            raise CanvasError("top and bottom canvas margins must leave usable height")
        if self.left_margin_pct + self.right_margin_pct >= 100:
            raise CanvasError("left and right canvas margins must leave usable width")

    def pixel_margins(self, size: Tuple[int, int]) -> Tuple[int, int, int, int]:
        width, height = size
        left = round(width * self.left_margin_pct / 100)
        right = round(width * self.right_margin_pct / 100)
        top = round(height * self.top_margin_pct / 100)
        bottom = round(height * self.bottom_margin_pct / 100)
        return left, top, right, bottom


DEFAULT_CANVAS = CanvasConfig()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element, name: str) -> Optional[str]:
    for child in element.iter():
        if _local_name(child.tag) == name:
            return child.text
    return None


def _normal_zip_path(path: str) -> str:
    path = unquote(path.split("#", 1)[0])
    normalized = posixpath.normpath(path)
    return normalized[2:] if normalized.startswith("./") else normalized


def _resolve_href(document_path: str, href: str) -> str:
    return _normal_zip_path(
        posixpath.join(posixpath.dirname(document_path), href)
    )


def _profile_size(profile: str, hq: bool, landscape: bool = False) -> Tuple[int, int]:
    if profile != "K11":
        raise CanvasError("canvas support currently targets only the K11 profile")
    scale = HQ_SCALE if hq else 1.0
    width = round(K11_LOGICAL_SIZE[0] * scale)
    height = round(K11_LOGICAL_SIZE[1] * scale)
    return (height, width) if landscape else (width, height)


def _logical_size(profile: str, landscape: bool = False) -> Tuple[int, int]:
    if profile != "K11":
        raise CanvasError("canvas support currently targets only the K11 profile")
    width, height = K11_LOGICAL_SIZE
    return (height, width) if landscape else (width, height)


def _prepare_image(image: Image.Image) -> Image.Image:
    if image.mode in ("L", "RGB"):
        return image
    if image.mode == "1":
        return image.convert("L")
    return image.convert("RGB")


def _border_samples(image: Image.Image) -> Iterable[Tuple[int, ...]]:
    image = _prepare_image(image)
    width, height = image.size
    step = max(1, min(width, height) // 64)
    points = set()
    for x in range(0, width, step):
        points.add((x, 0))
        points.add((x, height - 1))
    for y in range(0, height, step):
        points.add((0, y))
        points.add((width - 1, y))
    return (image.getpixel(point) for point in points)


def detect_background(image: Image.Image):
    """Estimate the page background from pixels touching the source border."""

    image = _prepare_image(image)
    samples = list(_border_samples(image))
    if not samples:
        return 255 if image.mode == "L" else (255, 255, 255)
    if image.mode == "L":
        return int(round(median(samples)))
    channels = zip(*samples)
    return tuple(int(round(median(channel))) for channel in channels)


def fit_image_to_canvas(
    image: Image.Image,
    target_size: Tuple[int, int],
    config: CanvasConfig,
    allow_upscale: bool = True,
) -> Image.Image:
    """Fit an image into a fixed canvas without cropping or distortion."""

    image = _prepare_image(image)
    canvas_width, canvas_height = target_size
    left, top, right, bottom = config.pixel_margins(target_size)
    safe_width = canvas_width - left - right
    safe_height = canvas_height - top - bottom
    if safe_width <= 0 or safe_height <= 0:
        raise CanvasError("canvas margins leave no usable content area")

    image_width, image_height = image.size
    ratio = min(safe_width / image_width, safe_height / image_height)
    if not allow_upscale:
        ratio = min(ratio, 1.0)
    resized_size = (
        max(1, round(image_width * ratio)),
        max(1, round(image_height * ratio)),
    )
    if resized_size == image.size:
        resized = image.copy()
    else:
        method = Image.Resampling.LANCZOS if ratio < 1 else Image.Resampling.BICUBIC
        resized = image.resize(resized_size, method)

    canvas = Image.new(image.mode, target_size, detect_background(image))
    offset = (
        left + max(0, safe_width - resized.width) // 2,
        top + max(0, safe_height - resized.height) // 2,
    )
    canvas.paste(resized, offset)
    return canvas


def normalize_image_bytes(
    data: bytes,
    target_size: Tuple[int, int],
    config: CanvasConfig,
    allow_upscale: bool = True,
) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = fit_image_to_canvas(source, target_size, config, allow_upscale)
        output = BytesIO()
        image_format = (source.format or "JPEG").upper()
        if image_format in ("JPG", "JPEG"):
            image.save(output, format="JPEG", quality=95, optimize=True)
        elif image_format == "PNG":
            image.save(output, format="PNG", optimize=True)
        else:
            image.save(output, format="JPEG", quality=95, optimize=True)
        return output.getvalue()


def _manifest_data(opf_root: ET.Element):
    manifest = {}
    for item in opf_root.iter():
        if _local_name(item.tag) == "item":
            item_id = item.get("id")
            if item_id:
                manifest[item_id] = item
    return manifest


def _cover_image_paths(opf_root: ET.Element, manifest: Dict[str, ET.Element], opf_path: str):
    cover_ids = set()
    cover_paths = set()
    for item_id, item in manifest.items():
        if "cover-image" in (item.get("properties") or "").split():
            cover_ids.add(item_id)
    for meta in opf_root.iter():
        if _local_name(meta.tag) == "meta" and meta.get("name") == "cover":
            if meta.get("content"):
                cover_ids.add(meta.get("content"))
    for item_id in cover_ids:
        item = manifest.get(item_id)
        if item is not None and item.get("href"):
            cover_paths.add(_resolve_href(opf_path, item.get("href")))
    return cover_paths


def _serialize_xml(root: ET.Element) -> bytes:
    # Other EPUB libraries can register their own default namespace globally;
    # restore the XHTML default before serializing the page document.
    ET.register_namespace("", XHTML_NS)
    ET.register_namespace("epub", EPUB_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _update_document_dimensions(
    document: ET.Element,
    image_dimensions: Dict[str, Tuple[int, int]],
    document_path: str,
    profile: str,
) -> bool:
    display_size = None
    for image in document.iter():
        if _local_name(image.tag) != "img":
            continue
        src = image.get("src")
        if not src:
            continue
        image_path = _resolve_href(document_path, src)
        target = image_dimensions.get(image_path)
        if target is None:
            continue
        width, height = _logical_size(profile, landscape=target[0] > target[1])
        image.set("width", str(width))
        image.set("height", str(height))
        display_size = display_size or (width, height)

    if display_size is None:
        return False

    logical_width, logical_height = display_size
    viewport = f"width={logical_width}, height={logical_height}"
    viewport_nodes = [
        node
        for node in document.iter()
        if _local_name(node.tag) == "meta" and (node.get("name") or "").lower() == "viewport"
    ]
    if viewport_nodes:
        viewport_nodes[0].set("content", viewport)
    else:
        head = next((node for node in document.iter() if _local_name(node.tag) == "head"), None)
        if head is not None:
            ET.SubElement(head, f"{{{XHTML_NS}}}meta", {"name": "viewport", "content": viewport})
    return True


def normalize_epub(
    epub_path: Path,
    config: CanvasConfig,
    profile: str = "K11",
    hq: bool = True,
    allow_upscale: bool = True,
) -> Path:
    """Normalize content pages in an EPUB and atomically replace the file."""

    if not config.enabled:
        return epub_path
    if profile != "K11":
        raise CanvasError("canvas support currently targets only the K11 profile")
    epub_path = Path(epub_path)
    if epub_path.suffix.lower() != ".epub":
        raise CanvasError("canvas normalization requires an EPUB output")

    with zipfile.ZipFile(epub_path, "r") as archive:
        entries = {info.filename: archive.read(info.filename) for info in archive.infolist()}

    container_name = "META-INF/container.xml"
    if container_name not in entries:
        raise CanvasError("EPUB is missing META-INF/container.xml")
    container_root = ET.fromstring(entries[container_name])
    rootfile = next(
        (node for node in container_root.iter() if _local_name(node.tag) == "rootfile"),
        None,
    )
    opf_path = _normal_zip_path(rootfile.get("full-path")) if rootfile is not None else ""
    if not opf_path or opf_path not in entries:
        raise CanvasError("EPUB package document could not be located")

    opf_root = ET.fromstring(entries[opf_path])
    manifest = _manifest_data(opf_root)
    cover_paths = _cover_image_paths(opf_root, manifest, opf_path)

    spine_documents = []
    spine = next((node for node in opf_root.iter() if _local_name(node.tag) == "spine"), None)
    if spine is not None:
        for itemref in spine:
            if _local_name(itemref.tag) != "itemref":
                continue
            item = manifest.get(itemref.get("idref"))
            if item is None or "xhtml" not in (item.get("media-type") or ""):
                continue
            path = _resolve_href(opf_path, item.get("href"))
            if path in entries:
                spine_documents.append((path, itemref.get("idref")))

    image_targets: Dict[str, Tuple[int, int]] = {}
    document_roots = {}
    for document_path, item_id in spine_documents:
        root = ET.fromstring(entries[document_path])
        document_roots[document_path] = root
        is_cover_document = item_id.lower() == "cover" if item_id else False
        if is_cover_document:
            continue
        for image in root.iter():
            if _local_name(image.tag) != "img" or not image.get("src"):
                continue
            image_path = _resolve_href(document_path, image.get("src"))
            if image_path not in entries or image_path in cover_paths:
                continue
            with Image.open(BytesIO(entries[image_path])) as source:
                landscape = source.width > source.height
            image_targets[image_path] = _profile_size(profile, hq, landscape)

    if not image_targets:
        raise CanvasError("EPUB contains no content images eligible for canvas normalization")

    for image_path, target_size in image_targets.items():
        entries[image_path] = normalize_image_bytes(
            entries[image_path],
            target_size,
            config,
            allow_upscale=allow_upscale,
        )

    for document_path, root in document_roots.items():
        if _update_document_dimensions(root, image_targets, document_path, profile):
            entries[document_path] = _serialize_xml(root)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{epub_path.name}.",
            suffix=".tmp",
            dir=epub_path.parent,
            delete=False,
        ) as temporary:
            temp_path = Path(temporary.name)
        with zipfile.ZipFile(temp_path, "w") as output:
            if "mimetype" not in entries:
                raise CanvasError("EPUB is missing the required mimetype entry")
            output.writestr("mimetype", entries["mimetype"], compress_type=zipfile.ZIP_STORED)
            for name, data in entries.items():
                if name == "mimetype":
                    continue
                output.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(temp_path, epub_path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return epub_path
