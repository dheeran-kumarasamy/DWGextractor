from pathlib import Path

from app.config import AppConfig
from app.loader import load_file
from app.pipeline import run_pipeline


def test_pipeline_decodes_legend_and_wall_types():
    config = AppConfig.from_env()
    fixture = Path(__file__).resolve().parent / "fixtures" / "legend_wall_fixture.dxf"
    loaded = load_file(fixture, config)
    report = run_pipeline(loaded.doc, loaded.unit_context)

    assert len(report.get("legend", [])) == 4
    labels = {entry["label"] for entry in report["legend"]}
    assert {"RC Column", "Compound Wall", "Gypsum Wall", "Steel Column"}.issubset(labels)

    wall_types = report.get("wall_types", [])
    assert any(entry["label"] == "Compound Wall" for entry in wall_types)
    assert any(entry["label"] == "RC Column" for entry in wall_types)
    assert report.get("columns") is not None
    assert len(report["columns"]) >= 1


def test_line_based_wall_extraction():
    import ezdxf
    from app.units import UnitContext
    from app.extractors.walls import WallExtractor

    doc = ezdxf.new()
    msp = doc.modelspace()

    # Create two parallel lines on "IC_wall" layer, separated by 9.0 inches.
    # Set the unit context to inches (so 9 inches = 228.6 mm)
    # Line A: (0, 0) to (100, 0)
    # Line B: (0, 9) to (100, 9)
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "IC_wall"})
    msp.add_line((0, 9), (100, 9), dxfattribs={"layer": "IC_wall"})

    # Create another pair of parallel lines separated by 4.5 inches (114.3 mm)
    # Line C: (200, 20) to (250, 20)
    # Line D: (200, 24.5) to (250, 24.5)
    msp.add_line((200, 20), (250, 20), dxfattribs={"layer": "IC_wall"})
    msp.add_line((200, 24.5), (250, 24.5), dxfattribs={"layer": "IC_wall"})

    unit_context = UnitContext(source_unit="inch", to_mm=25.4, is_imperial=True)
    ctx = {
        "unit_context": unit_context,
        "legend": [],
        "legend_x_range": None
    }

    extractor = WallExtractor()
    result = extractor.extract(doc, ctx)

    assert result["status"] == "ok"
    wall_types = result["data"]["wall_types"]
    assert len(wall_types) == 2

    # Verify thickness of extracted wall types (228.6 mm and 114.3 mm)
    thicknesses = {wt["thickness_mm"] for wt in wall_types}
    assert 228.6 in thicknesses
    assert 114.3 in thicknesses

    # Verify count is 1 for each
    for wt in wall_types:
        assert wt["count"] == 1
        assert wt["role"] == "wall"
        assert "IC_wall" in wt["label"]

    assert len(result["warnings"]) == 1
    assert "No walls found via hatch entities" in result["warnings"][0]
