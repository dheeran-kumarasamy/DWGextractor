from __future__ import annotations

from app.extractors.base import BaseExtractor
from app.extractors.legend import LegendExtractor
from app.extractors.walls import WallExtractor

EXTRACTOR_REGISTRY: list[BaseExtractor] = [
    LegendExtractor(),
    WallExtractor(),
]
