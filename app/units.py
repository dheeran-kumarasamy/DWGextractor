from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


INSUNITS_TO_MM: Dict[int, Tuple[str, float]] = {
    0: ("unitless", 1.0),
    1: ("inch", 25.4),
    2: ("foot", 304.8),
    3: ("mile", 1609344.0),
    4: ("millimeter", 1.0),
    5: ("centimeter", 10.0),
    6: ("meter", 1000.0),
    7: ("kilometer", 1000000.0),
    8: ("microinch", 0.0000254),
    9: ("mil", 0.0254),
    10: ("yard", 914.4),
    11: ("angstrom", 0.0000001),
    12: ("nanometer", 0.000001),
    13: ("micrometer", 0.001),
    14: ("decimeter", 100.0),
    15: ("decameter", 10000.0),
    16: ("hectometer", 100000.0),
    17: ("gigameter", 1000000000000.0),
    18: ("astronomical unit", 149597870700000.0),
    19: ("light year", 9460730472580800.0),
    20: ("parsec", 30856775814913600.0),
}


@dataclass(frozen=True)
class UnitContext:
    to_mm: float
    source_unit: str
    is_imperial: bool


def build_unit_context(doc) -> tuple["UnitContext", list[str]]:
    warnings: list[str] = []
    units_code = int(doc.header.get("$INSUNITS", 0) or 0)
    source_unit, to_mm = INSUNITS_TO_MM.get(units_code, ("unknown", 1.0))
    if units_code == 0:
        warnings.append(
            "$INSUNITS is unset or unitless: assuming millimetres for ingestion."
        )
    if units_code not in INSUNITS_TO_MM:
        warnings.append(
            f"Unrecognized $INSUNITS={units_code}: defaulting to {source_unit} with 1.0mm scaling."
        )
    is_imperial = units_code == 1
    return UnitContext(to_mm=to_mm, source_unit=source_unit, is_imperial=is_imperial), warnings
