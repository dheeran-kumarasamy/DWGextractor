from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseExtractor(ABC):
    name: str
    enabled: bool = True

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def extract(self, doc: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
        ...


def extractor_result(data: Dict[str, Any], warnings: List[str] | None = None) -> Dict[str, Any]:
    return {
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
    }
