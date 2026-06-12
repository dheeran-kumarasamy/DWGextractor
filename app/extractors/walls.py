from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import ezdxf

from app.extractors.base import BaseExtractor, extractor_result
from app.hatch_signature import angles_match, hatch_signature, signature_key
from app.units import UnitContext

WALL_LAYER_TOKENS = ["wall", "partition", "masonry", "brick", "concrete"]
STAIR_SPACING_MM = 267.0
MIN_SEGMENT_MM = 50.0


def _normalize_layer(layer: str) -> str:
    return (layer or "").strip().lower()


def _is_wall_layer(layer: str) -> bool:
    text = _normalize_layer(layer)
    return any(token in text for token in WALL_LAYER_TOKENS)


def _point_xy(point: Tuple[float, float, float]) -> Tuple[float, float]:
    return float(point[0]), float(point[1])


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _path_edges(path: ezdxf.entities.boundary_paths.PolylinePath, ctx: UnitContext) -> List[float]:
    if not hasattr(path, "vertices") or not path.vertices:
        return []
    points = [_point_xy(vertex) for vertex in path.vertices]
    edges: List[float] = []
    for first, second in zip(points, points[1:]):
        edges.append(_distance((first[0] * ctx.to_mm, first[1] * ctx.to_mm), (second[0] * ctx.to_mm, second[1] * ctx.to_mm)))
    if len(points) > 1 and points[0] != points[-1]:
        edges.append(_distance((points[-1][0] * ctx.to_mm, points[-1][1] * ctx.to_mm), (points[0][0] * ctx.to_mm, points[0][1] * ctx.to_mm)))
    return edges


def _hatch_edge_lengths(hatch: ezdxf.entities.Hatch, ctx: UnitContext) -> List[float]:
    lengths: List[float] = []
    for path in hatch.paths:
        lengths.extend(_path_edges(path, ctx))
    return lengths


def _hatch_bounds(hatch: ezdxf.entities.Hatch, ctx: UnitContext) -> Optional[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for path in hatch.paths:
        if hasattr(path, "vertices") and path.vertices:
            for vertex in path.vertices:
                x, y = _point_xy(vertex)
                points.append((x * ctx.to_mm, y * ctx.to_mm))
    if not points:
        return None
    xs, ys = zip(*points)
    return max(xs) - min(xs), max(ys) - min(ys)


def _hatch_min_dimension_mm(hatch: ezdxf.entities.Hatch, ctx: UnitContext) -> float:
    edges = [edge for edge in _hatch_edge_lengths(hatch, ctx) if edge > 0.0]
    dimensions: List[float] = []
    if edges:
        dimensions.append(min(edges))
    bounds = _hatch_bounds(hatch, ctx)
    if bounds is not None:
        width, height = bounds
        if width > 0.0 and height > 0.0:
            dimensions.append(min(width, height))
    return min(dimensions) if dimensions else 0.0


def _hatch_center(hatch: ezdxf.entities.Hatch, ctx: UnitContext) -> Optional[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for path in hatch.paths:
        if hasattr(path, "vertices") and path.vertices:
            for vertex in path.vertices:
                x, y = _point_xy(vertex)
                points.append((x * ctx.to_mm, y * ctx.to_mm))
    if not points:
        return None
    xs, ys = zip(*points)
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _is_legend_hatch(hatch: ezdxf.entities.Hatch, legend_x_range: Optional[Sequence[float]], ctx: UnitContext) -> bool:
    center = _hatch_center(hatch, ctx)
    if center is None or legend_x_range is None:
        return False
    x = center[0]
    return legend_x_range[0] <= x <= legend_x_range[1]


def _line_direction(line: ezdxf.entities.Line) -> Tuple[float, float]:
    start = _point_xy(line.dxf.start)
    end = _point_xy(line.dxf.end)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


def _line_angle(line: ezdxf.entities.Line) -> float:
    dx, dy = _line_direction(line)
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    return angle


def _point_line_distance(point: Tuple[float, float], line: ezdxf.entities.Line) -> float:
    start = _point_xy(line.dxf.start)
    end = _point_xy(line.dxf.end)
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return _distance(point, start)
    num = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1)
    den = math.hypot(dx, dy)
    return (num / den) * 1.0


def _line_midpoint(line: ezdxf.entities.Line, ctx: UnitContext) -> Tuple[float, float]:
    start = _point_xy(line.dxf.start)
    end = _point_xy(line.dxf.end)
    return ((start[0] + end[0]) / 2.0 * ctx.to_mm, (start[1] + end[1]) / 2.0 * ctx.to_mm)


def _stair_candidate(distance_mm: float) -> bool:
    return abs(distance_mm - STAIR_SPACING_MM) <= 15.0


def _get_line_params(line: Any, ctx: UnitContext) -> Optional[Tuple[float, float, float, float, float, float, float]]:
    if not hasattr(line, "dxf") or not hasattr(line.dxf, "start") or not hasattr(line.dxf, "end"):
        return None
    start = _point_xy(line.dxf.start)
    end = _point_xy(line.dxf.end)
    x1, y1 = start[0] * ctx.to_mm, start[1] * ctx.to_mm
    x2, y2 = end[0] * ctx.to_mm, end[1] * ctx.to_mm
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    ux = dx / length
    uy = dy / length
    return (x1, y1, x2, y2, ux, uy, length)


def _is_parallel_wall_pair(line_a: Any, line_b: Any, ctx: UnitContext) -> Optional[float]:
    params_a = _get_line_params(line_a, ctx)
    params_b = _get_line_params(line_b, ctx)
    if not params_a or not params_b:
        return None

    x1_a, y1_a, x2_a, y2_a, ux_a, uy_a, len_a = params_a
    x1_b, y1_b, x2_b, y2_b, ux_b, uy_b, len_b = params_b

    # Parallel check within ~5 degrees (cos(5 deg) ~ 0.996)
    dot = abs(ux_a * ux_b + uy_a * uy_b)
    if dot < 0.996:
        return None

    # Perpendicular distance:
    # Distance from start point of a to infinite line of b.
    # Normal vector of b is (-uy_b, ux_b)
    nx = -uy_b
    ny = ux_b
    dist = abs((x1_a - x1_b) * nx + (y1_a - y1_b) * ny)

    # Realistic wall thickness constraints
    if not (50.0 <= dist <= 600.0):
        return None

    if _stair_candidate(dist):
        return None

    # Projection/Overlap check:
    # Project endpoints onto unit vector (ux_b, uy_b)
    proj_a1 = x1_a * ux_b + y1_a * uy_b
    proj_a2 = x2_a * ux_b + y2_a * uy_b
    proj_b1 = x1_b * ux_b + y1_b * uy_b
    proj_b2 = x2_b * ux_b + y2_b * uy_b

    min_a, max_a = min(proj_a1, proj_a2), max(proj_a1, proj_a2)
    min_b, max_b = min(proj_b1, proj_b2), max(proj_b1, proj_b2)

    overlap = min(max_a, max_b) - max(min_a, min_b)
    if overlap < 50.0:
        return None

    return dist


def _line_thickness_candidates(doc: Any, ctx: UnitContext) -> List[float]:
    lines = [entity for entity in doc.modelspace() if entity.dxftype() == "LINE" and _is_wall_layer(entity.dxf.layer)]
    candidates: List[float] = []
    for line_a, line_b in itertools.combinations(lines, 2):
        if not angles_match(_line_angle(line_a), _line_angle(line_b)):
            continue
        midpoint = _line_midpoint(line_a, ctx)
        dist = _point_line_distance(midpoint, line_b) * ctx.to_mm
        if dist < MIN_SEGMENT_MM or _stair_candidate(dist):
            continue
        candidates.append(dist)
    return sorted(set(round(c, 2) for c in candidates if c > 0.0))


def _confirm_thickness(estimated: float, candidates: Sequence[float]) -> float:
    for candidate in candidates:
        if abs(candidate - estimated) <= max(estimated * 0.15, 5.0):
            return candidate
    return estimated


def _segment_lengths(edges: List[float]) -> List[float]:
    if not edges:
        return []
    max_length = max(edges)
    threshold = max(max_length * 0.5, MIN_SEGMENT_MM)
    return sorted({round(edge, 2) for edge in edges if edge >= threshold and edge >= MIN_SEGMENT_MM})


def _extract_block_hatches(doc: Any, ctx: UnitContext) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for insert in doc.modelspace().query("INSERT"):
        block_name = insert.dxf.name
        if block_name not in doc.blocks:
            continue
        block = doc.blocks[block_name]
        for hatch in block.query("HATCH"):
            sig = hatch_signature(hatch)
            thickness = _hatch_min_dimension_mm(hatch, ctx)
            if thickness <= 0.0:
                continue
            results.append(
                {
                    "signature": sig,
                    "signature_key": signature_key(sig),
                    "thickness_mm": round(thickness, 2),
                    "count": 1,
                    "role": "column",
                    "label": "column",
                }
            )
    return results


class WallExtractor(BaseExtractor):
    def __init__(self) -> None:
        super().__init__("walls")

    def extract(self, doc: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
        unit_ctx: UnitContext = ctx["unit_context"]
        legend_rows: List[Dict[str, Any]] = ctx.get("legend", [])
        legend_x_range: Optional[Sequence[float]] = ctx.get("legend_x_range")

        legend_map = {tuple(row["signature_key"]): row for row in legend_rows}
        plan_hatches = []
        for entity in doc.modelspace().query("HATCH"):
            if _is_legend_hatch(entity, legend_x_range, unit_ctx):
                continue
            plan_hatches.append(entity)

        wall_types: Dict[Tuple[str, float], Dict[str, Any]] = {}
        line_thicknesses = _line_thickness_candidates(doc, unit_ctx)

        for hatch in plan_hatches:
            sig = hatch_signature(hatch)
            key = signature_key(sig)
            mapped = legend_map.get(key)
            if mapped is None:
                mapped = next(
                    (
                        row
                        for row in legend_rows
                        if row["signature"]["pattern"] == sig["pattern"]
                        and angles_match(row["signature"]["angle"], sig["angle"])
                    ),
                    None,
                )
            if mapped is None:
                continue
            role = mapped.get("role", "wall")
            if role not in {"wall", "column"}:
                continue

            edges = _hatch_edge_lengths(hatch, unit_ctx)
            if not edges:
                continue
            thickness = min((edge for edge in edges if edge >= MIN_SEGMENT_MM), default=0.0)
            if thickness <= 0.0:
                continue
            thickness = _confirm_thickness(thickness, line_thicknesses)
            segments = _segment_lengths(edges)
            if not segments:
                continue

            type_row = wall_types.setdefault(
                key,
                {
                    "label": mapped.get("label", "unknown"),
                    "role": role,
                    "signature": sig,
                    "thickness_mm": 0.0,
                    "segment_lengths_mm": [],
                    "count": 0,
                },
            )
            type_row["count"] += 1
            type_row["thickness_mm"] = round(thickness, 2)
            type_row["segment_lengths_mm"] = sorted({*type_row["segment_lengths_mm"], *segments})

        warnings: List[str] = []
        # Fallback to line-based wall extraction if no wall types were extracted from hatches
        if not wall_types:
            wall_lines = [
                entity
                for entity in doc.modelspace()
                if entity.dxftype() == "LINE" and _is_wall_layer(entity.dxf.layer)
            ]

            pairs = []
            for line_a, line_b in itertools.combinations(wall_lines, 2):
                dist = _is_parallel_wall_pair(line_a, line_b, unit_ctx)
                if dist is not None:
                    pairs.append((line_a, line_b, dist))

            grouped_thicknesses: Dict[float, List[Tuple[Any, Any]]] = {}
            for la, lb, dist in pairs:
                matched_thickness = None
                for t in grouped_thicknesses.keys():
                    if abs(t - dist) <= 5.0:
                        matched_thickness = t
                        break
                if matched_thickness is None:
                    matched_thickness = round(dist, 1)
                    grouped_thicknesses[matched_thickness] = []
                grouped_thicknesses[matched_thickness].append((la, lb))

            if grouped_thicknesses:
                warnings.append(
                    "No walls found via hatch entities; fell back to line-based wall extraction."
                )

            for thickness, p_list in grouped_thicknesses.items():
                segment_lengths = set()
                layers = set()
                for la, lb in p_list:
                    layers.add(la.dxf.layer)
                    layers.add(lb.dxf.layer)

                    params_a = _get_line_params(la, unit_ctx)
                    params_b = _get_line_params(lb, unit_ctx)
                    if params_a:
                        segment_lengths.add(round(params_a[6], 2))
                    if params_b:
                        segment_lengths.add(round(params_b[6], 2))

                layer_name = sorted(list(layers))[0] if layers else "wall_layer"

                sig = {
                    "pattern": "LINE",
                    "solid": False,
                    "angle": 0.0,
                    "angle_bucket": 0.0,
                    "color": 256,
                    "scale": 1.0,
                    "layer": layer_name,
                }
                key = (f"LINE_{thickness}", 0.0)

                wall_types[key] = {
                    "label": f"Wall ({layer_name}, {thickness}mm)",
                    "role": "wall",
                    "signature": sig,
                    "thickness_mm": round(thickness, 2),
                    "segment_lengths_mm": sorted(list(segment_lengths)),
                    "count": len(p_list),
                }

        columns = _extract_block_hatches(doc, unit_ctx)
        data = {
            "wall_types": list(wall_types.values()),
            "columns": columns,
            "line_thickness_candidates_mm": line_thicknesses,
        }
        return extractor_result(data, warnings)
