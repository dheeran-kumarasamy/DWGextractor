from __future__ import annotations

ANGLE_TOL = 5.0  # degrees


def _get(dxfns, name, default=None):
    try:
        return dxfns.get(name, default)
    except Exception:
        return getattr(dxfns, name, default)


def effective_pattern_angle(hatch):
    """Visible angle of the dominant hatch-line family, normalized to [0,180).

    Robust to whether rotation is in pattern_angle (group 52) or baked into the
    pattern-line definitions (group 53). Compute it identically for legend
    swatches and plan hatches so the two ANSI31 uses separate cleanly."""
    base = float(_get(hatch.dxf, "pattern_angle", 0.0) or 0.0)
    line_angle = 0.0
    pattern = getattr(hatch, "pattern", None)
    if pattern is not None and getattr(pattern, "lines", None):
        line_angle = float(getattr(pattern.lines[0], "angle", 0.0) or 0.0)
    return (base + line_angle) % 180.0


def hatch_signature(hatch):
    """Position-independent fill identity. Classify on THIS — never on position,
    never on block name (block names are hash-encoded and meaningless)."""
    solid = bool(_get(hatch.dxf, "solid_fill", 0))
    name = (_get(hatch.dxf, "pattern_name", "") or "").strip().upper()
    if solid and not name:
        name = "SOLID"
    angle = effective_pattern_angle(hatch)
    angle_bucket = round(angle / ANGLE_TOL) * ANGLE_TOL % 180.0
    return {
        "pattern": name,
        "solid": solid,
        "angle": round(angle, 2),
        "angle_bucket": round(angle_bucket, 2),
        "color": _get(hatch.dxf, "color", 256),
        "scale": round(float(_get(hatch.dxf, "pattern_scale", 1.0) or 1.0), 4),
        "layer": _get(hatch.dxf, "layer", ""),
    }


def signature_key(sig):
    return (sig["pattern"], sig["angle_bucket"])


def angles_match(a, b, tol=ANGLE_TOL):
    d = abs((a - b) % 180.0)
    return min(d, 180.0 - d) <= tol


def infer_role_from_label(label: str) -> str:
    searchable = (label or "").lower()
    if any(token in searchable for token in ["column", "col"]):
        return "column"
    return "wall"
