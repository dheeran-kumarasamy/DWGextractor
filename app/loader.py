from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import ezdxf
from ezdxf import recover

from app.config import AppConfig
from app.units import UnitContext, build_unit_context


class LoaderError(RuntimeError):
    pass


@dataclass
class LoadedDrawing:
    doc: ezdxf.document.Drawing
    auditor: object
    unit_context: UnitContext
    warnings: List[str]
    source_kind: str
    source_path: Path


def _resolve_executable(path: Optional[str]) -> Optional[Path]:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    if candidate.is_dir():
        for exe in (
            candidate / "Contents" / "MacOS" / candidate.name,
            candidate / "Contents" / "MacOS" / "ODAFileConverter",
            candidate / "Contents" / "MacOS" / "TeighaFileConverter",
        ):
            if exe.is_file() and os.access(exe, os.X_OK):
                return exe
    return None


def _read_dxf(path: Path) -> tuple[ezdxf.document.Drawing, object, List[str]]:
    try:
        doc, auditor = recover.readfile(str(path))
    except Exception as exc:
        raise LoaderError(f"Failed reading DXF: {exc}") from exc

    warnings: List[str] = []
    if hasattr(auditor, "errors") and auditor.errors:
        warnings.append(
            "DXF audit found recoverable errors; output may be incomplete. "
            "Run EXPORTTOAUTOCAD before export if the source is AEC-derived."
        )
        for error in auditor.errors:
            warnings.append(str(error))
    return doc, auditor, warnings


def _run_converter(
    converter: Path,
    dwg_path: Path,
    output_version: str,
    temp_dir: Optional[Path],
) -> tuple[Path, List[str]]:
    if not converter.exists() or not os.access(converter, os.X_OK):
        raise LoaderError(
            f"ODA converter path is not executable: {converter}. "
            "Set ODA_CONVERTER_PATH to the full executable and retry."
        )

    if temp_dir:
        work_dir = Path(temp_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = Path(tempfile.mkdtemp())

    src_dir = work_dir / "src"
    out_dir = work_dir / "out"
    src_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dwg_path, src_dir / dwg_path.name)

    cmd = [
        str(converter),
        str(src_dir),
        str(out_dir),
        output_version,
        "DXF",
        "0",
        "1",
    ]
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    notes: List[str] = []
    if proc.stdout:
        notes.append(proc.stdout.strip())
    if proc.stderr:
        notes.append(proc.stderr.strip())

    dxf_candidates = sorted(out_dir.rglob("*.dxf"))
    if proc.returncode != 0 or not dxf_candidates:
        raise LoaderError(
            "ODA File Converter failed to produce DXF. "
            f"Command output: {' | '.join(notes)}"
        )
    return dxf_candidates[0], notes


def load_file(path: Path, config: AppConfig) -> LoadedDrawing:
    ext = path.suffix.lower()
    if ext == ".dxf":
        doc, auditor, warnings = _read_dxf(path)
        unit_context, unit_warnings = build_unit_context(doc)
        warnings.extend(unit_warnings)
        return LoadedDrawing(
            doc=doc,
            auditor=auditor,
            unit_context=unit_context,
            warnings=warnings,
            source_kind="dxf",
            source_path=path,
        )

    if ext != ".dwg":
        raise LoaderError(f"Unsupported file type: {ext}")

    converter_path = _resolve_executable(config.oda_converter_path)
    if converter_path is None:
        raise LoaderError(
            "ODA_CONVERTER_PATH is not set or does not point to a valid executable. "
            "Upload a DXF instead, or configure the ODA File Converter path."
        )

    with tempfile.TemporaryDirectory(dir=config.temp_dir) as td:
        dxf_path, notes = _run_converter(
            converter=converter_path,
            dwg_path=path,
            output_version=config.oda_output_version,
            temp_dir=Path(td),
        )
        warnings = [f"ODA conversion: {note}" for note in notes if note]
        doc, auditor, dxf_warnings = _read_dxf(dxf_path)
        warnings.extend(dxf_warnings)
        unit_context, unit_warnings = build_unit_context(doc)
        warnings.extend(unit_warnings)
        return LoadedDrawing(
            doc=doc,
            auditor=auditor,
            unit_context=unit_context,
            warnings=warnings,
            source_kind="dwg",
            source_path=path,
        )

    raise LoaderError("Unexpected error while loading input file.")
