from __future__ import annotations

from typing import Any, Dict, List

from app.extractors import EXTRACTOR_REGISTRY


def run_pipeline(doc: Any, unit_context: Any) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {"unit_context": unit_context}
    report: Dict[str, Any] = {}
    warnings: List[str] = []

    for extractor in EXTRACTOR_REGISTRY:
        result = extractor.extract(doc, ctx)
        warnings.extend(result.get("warnings", []))
        data = result.get("data", {})
        report.update(data)

        if extractor.name == "legend":
            ctx["legend"] = data.get("legend", [])
            ctx["legend_x_range"] = data.get("legend_x_range")

    report["warnings"] = warnings
    return report
