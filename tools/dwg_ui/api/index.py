from __future__ import annotations

import html
import tempfile
from pathlib import Path
from typing import Dict, List

from flask import Flask, Response, request

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractor import ExtractionError, extract_entities_and_layers  # noqa: E402

app = Flask(__name__)


def _render_table(title: str, rows: List[Dict[str, str]]) -> str:
    if not rows:
        return f"<h3>{html.escape(title)}</h3><p>No rows.</p>"

    columns = list(rows[0].keys())
    head_cells = "".join(f"<th>{html.escape(col)}</th>" for col in columns)

    body_rows = []
    for row in rows[:2000]:
        cells = "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")

    return (
        f"<h3>{html.escape(title)}</h3>"
        "<div style='overflow:auto; max-height:360px; border:1px solid #ddd; border-radius:8px;'>"
        "<table style='border-collapse:collapse; width:100%; font-family:Arial, sans-serif; font-size:13px;'>"
        f"<thead><tr style='background:#f6f8fa'>{head_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


@app.get("/")
def home() -> Response:
    return Response(
        """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>DWG Extractor</title>
</head>
<body style='font-family:Arial, sans-serif; margin:32px; max-width:980px;'>
  <h1>DWG/DXF Entity Extractor</h1>
  <p>Upload a DWG or DXF file to inspect entities and layers.</p>
  <p style='color:#666'>Note: Vercel runtime may not have native DWG converters, so DXF files are the most reliable in this deployment.</p>
  <form method='post' action='/extract' enctype='multipart/form-data'>
    <input type='file' name='file' accept='.dwg,.dxf' required>
    <button type='submit'>Extract</button>
  </form>
</body>
</html>
""",
        mimetype="text/html",
    )


@app.post("/extract")
def extract() -> Response:
    uploaded = request.files.get("file")
    if uploaded is None or uploaded.filename is None:
        return Response("No file uploaded", status=400)

    suffix = Path(uploaded.filename).suffix.lower()
    if suffix not in {".dwg", ".dxf"}:
        return Response("Only .dwg and .dxf files are supported", status=400)

    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / uploaded.filename
        input_path.write_bytes(uploaded.stream.read())

        try:
            result = extract_entities_and_layers(input_path=input_path, timeout_sec=30)
        except ExtractionError as exc:
            safe = html.escape(str(exc))
            return Response(
                f"<h2>Extraction failed</h2><pre>{safe}</pre><p><a href='/'>Back</a></p>",
                status=400,
                mimetype="text/html",
            )

    notes_html = "".join(f"<li>{html.escape(note)}</li>" for note in result.notes)
    feature_counts = result.feature_counts or {"walls": 0, "windows": 0, "doors": 0}
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>DWG Extractor Results</title></head>"
        "<body style='font-family:Arial, sans-serif; margin:32px; max-width:1200px;'>"
        f"<h2>Source: {html.escape(result.source_kind.upper())}</h2>"
        f"<p><strong>Walls:</strong> {int(feature_counts.get('walls', 0))} &nbsp; "
        f"<strong>Windows:</strong> {int(feature_counts.get('windows', 0))} &nbsp; "
        f"<strong>Doors:</strong> {int(feature_counts.get('doors', 0))}</p>"
        f"<p><a href='/'>Upload another file</a></p><ul>{notes_html}</ul>"
        f"{_render_table('Entities', result.entities)}"
        f"{_render_table('Features', result.feature_entities)}"
        f"{_render_table('Layers', result.layers)}"
        f"{_render_table('Entity Types', result.entity_types)}"
        "</body></html>"
    )
    return Response(body, mimetype="text/html")
