from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import ezdxf

from app.extractors.base import BaseExtractor, extractor_result
from app.hatch_signature import hatch_signature, infer_role_from_label, signature_key
from app.units import UnitContext


def _point_to_tuple(point: Tuple[float, float, float]) -> Tuple[float, float]:
    return float(point[0]), float(point[1])


def _path_points(path: Any) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    if hasattr(path, "vertices") and path.vertices:
        for vertex in path.vertices:
            points.append(_point_to_tuple(vertex))
        return points

    if hasattr(path, "edges") and path.edges:
        for edge in path.edges:
            start = None
            end = None
            for attr in ("start_point", "real_start_point", "start"):
                if hasattr(edge, attr):
                    start = getattr(edge, attr)
                    if start is not None:
                        break
            for attr in ("end_point", "real_end_point", "end"):
                if hasattr(edge, attr):
                    end = getattr(edge, attr)
                    if end is not None:
                        break
            if start is not None:
                points.append(_point_to_tuple(start))
            if end is not None:
                points.append(_point_to_tuple(end))
    return points


def _hatch_centroid(hatch: ezdxf.entities.Hatch, ctx: UnitContext) -> Optional[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for path in hatch.paths:
        points.extend(_path_points(path))
    if not points:
        return None
    xs, ys = zip(*points)
    return (sum(x * ctx.to_mm for x in xs) / len(xs), sum(y * ctx.to_mm for y in ys) / len(ys))


def _text_position(entity: ezdxf.entities.DXFGraphic, ctx: UnitContext) -> Optional[Tuple[float, float, str]]:
    text: str = ""
    if entity.dxftype() == "TEXT":
        text = str(entity.dxf.text or "").strip()
        insert = entity.dxf.insert
    elif entity.dxftype() == "MTEXT":
        text = str(entity.plain_text() if hasattr(entity, "plain_text") else entity.text or "").strip()
        insert = entity.dxf.insert
    else:
        return None
    if not text:
        return None
    x, y = float(insert[0]) * ctx.to_mm, float(insert[1]) * ctx.to_mm
    return x, y, text


def _cluster_hatches_by_x(hatches: List[Dict[str, Any]], tolerance: float) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    for hatch in hatches:
        x = hatch["center"][0]
        for group in groups:
            if abs(group[0]["center"][0] - x) <= tolerance:
                group.append(hatch)
                break
        else:
            groups.append([hatch])
    return sorted(groups, key=lambda group: -len(group))


def _map_labels_to_swatches(
    swatches: List[Dict[str, Any]], labels: List[Tuple[float, float, str]]
) -> List[Dict[str, Any]]:
    swatches_sorted = sorted(swatches, key=lambda item: -item["center"][1])
    labels_sorted = sorted(labels, key=lambda item: -item[1])
    rows: List[Dict[str, Any]] = []
    count = min(len(swatches_sorted), len(labels_sorted))
    for index in range(count):
        hatch = swatches_sorted[index]
        _, _, text = labels_sorted[index]
        sig = hatch_signature(hatch["entity"])
        rows.append(
            {
                "label": text,
                "role": infer_role_from_label(text),
                "signature": sig,
                "signature_key": signature_key(sig),
                "center": hatch["center"],
            }
        )
    return rows


class LegendExtractor(BaseExtractor):
    def __init__(self) -> None:
        super().__init__("legend")

    def extract(self, doc: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
        unit_ctx: UnitContext = ctx["unit_context"]
        msp = doc.modelspace()
        hatch_items: List[Dict[str, Any]] = []
        text_items: List[Tuple[float, float, str]] = []

        for entity in msp:
            if entity.dxftype() == "HATCH":
                center = _hatch_centroid(entity, unit_ctx)
                if center is not None:
                    hatch_items.append({"entity": entity, "center": center})
            elif entity.dxftype() in {"TEXT", "MTEXT"}:
                label = _text_position(entity, unit_ctx)
                if label is not None:
                    text_items.append(label)

        if not hatch_items:
            return extractor_result({"legend": [], "legend_x_range": None}, ["No legend hatches found."])

        tolerance = 25.0
        groups = _cluster_hatches_by_x(hatch_items, tolerance)
        best_group = groups[0] if groups else []
        if len(best_group) < 2:
            return extractor_result(
                {"legend": [], "legend_x_range": None},
                ["Legend could not be identified reliably from hatch X coordinates."],
            )

        legend_x_coords = [item["center"][0] for item in best_group]
        min_x, max_x = min(legend_x_coords), max(legend_x_coords)
        range_padding = max(25.0, (max_x - min_x) * 0.5)
        legend_x_range = [min_x - range_padding, max_x + range_padding]

        legend_rows = _map_labels_to_swatches(best_group, text_items)
        warnings: List[str] = []
        if not legend_rows:
            warnings.append(
                "Legend swatches were found, but identical count of text labels could not be matched."
            )

        return extractor_result(
            {
                "legend": legend_rows,
                "legend_x_range": legend_x_range,
            },
            warnings,
        )
