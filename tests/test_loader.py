from pathlib import Path

from app.config import AppConfig
from app.loader import load_file


def test_load_dxf_fixture_returns_doc_and_units():
    config = AppConfig.from_env()
    fixture = Path(__file__).resolve().parent / "fixtures" / "legend_wall_fixture.dxf"
    result = load_file(fixture, config)
    assert result.source_kind == "dxf"
    assert result.unit_context.to_mm == 1.0 or result.unit_context.source_unit in {"inch", "millimeter"}
    assert result.doc is not None
    assert isinstance(result.warnings, list)
