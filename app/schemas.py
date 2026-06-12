from __future__ import annotations

from typing import Any, List, Tuple

from pydantic import BaseModel


class LegendRow(BaseModel):
    label: str
    role: str
    signature: dict[str, Any]
    signature_key: Tuple[str, float]
    center: list[float]


class WallType(BaseModel):
    label: str
    role: str
    signature: dict[str, Any]
    thickness_mm: float
    segment_lengths_mm: List[float]
    count: int


class ColumnType(BaseModel):
    signature: dict[str, Any]
    thickness_mm: float
    count: int
    role: str
    label: str


class ExtractResponse(BaseModel):
    source_unit: str
    is_imperial: bool
    warnings: List[str]
    legend: List[LegendRow]
    legend_x_range: list[float] | None
    wall_types: List[WallType]
    columns: List[ColumnType]
    line_thickness_candidates_mm: List[float]
