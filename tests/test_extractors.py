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
