from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import AppConfig
from app.loader import LoaderError, load_file
from app.pipeline import run_pipeline
from app.schemas import ExtractResponse

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="DWG Floor Plan Extractor")


@app.post("/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".dwg", ".dxf"}:
        raise HTTPException(status_code=400, detail="Only .dwg and .dxf files are supported.")

    config = AppConfig.from_env()
    contents = await file.read()
    if len(contents) > config.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Upload size exceeds MAX_UPLOAD_MB={config.max_upload_mb}.",
        )

    with tempfile.TemporaryDirectory(dir=config.temp_dir) as td:
        input_path = Path(td) / file.filename
        input_path.write_bytes(contents)
        try:
            loaded = load_file(input_path, config)
        except LoaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    pipeline = run_pipeline(loaded.doc, loaded.unit_context)
    warnings: List[str] = [*loaded.warnings, *pipeline.get("warnings", [])]
    return ExtractResponse(
        source_unit=loaded.unit_context.source_unit,
        is_imperial=loaded.unit_context.is_imperial,
        warnings=warnings,
        legend=pipeline.get("legend", []),
        legend_x_range=pipeline.get("legend_x_range"),
        wall_types=pipeline.get("wall_types", []),
        columns=pipeline.get("columns", []),
        line_thickness_candidates_mm=pipeline.get("line_thickness_candidates_mm", []),
    )


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
