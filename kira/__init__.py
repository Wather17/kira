"""
Kira Manga Processing & Kindle Optimization Pipeline.
"""

__version__ = "0.1.0"
__author__ = "Kira Team"

from kira.pipeline import MangaPipeline
from kira.extractor import MangaExtractor
from kira.upscaler import MangaUpscaler
from kira.converter import KindleConverter
from kira.merger import VolumeMerger, AOT_VOLUME_MAPPING
from kira.metadata import MangaMetadata, set_custom_cover, optimize_volume_structure
from kira.providers import OnlineMangaProvider

__all__ = [
    "MangaPipeline",
    "MangaExtractor",
    "MangaUpscaler",
    "KindleConverter",
    "VolumeMerger",
    "AOT_VOLUME_MAPPING",
    "MangaMetadata",
    "set_custom_cover",
    "optimize_volume_structure",
    "OnlineMangaProvider",
]



