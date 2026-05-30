from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ezdxf
from ezdxf.addons import odafc


@dataclass
class ExtractionResult:
    entities: List[Dict[str, str]]
    layers: List[Dict[str, str]]
    entity_types: List[Dict[str, str]]
    source_kind: str
    notes: List[str]


class ExtractionError(RuntimeError):
    pass


def _elapsed_s(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def _saved_converter_config_path() -> Path:
    return Path(__file__).resolve().parent / ".converter-path"


def _read_saved_converter_path() -> Optional[str]:
    path = _saved_converter_config_path()
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def read_saved_converter_path() -> Optional[str]:
    return _read_saved_converter_path()


def configure_odafc(converter_bin: Optional[Path]) -> None:
    configured_path = None
    if converter_bin:
        configured_path = _resolve_executable_path(str(converter_bin))
    if not configured_path:
        configured_path = _resolve_executable_path(_read_saved_converter_path())
    if configured_path:
        ezdxf.options.set("odafc-addon", "unix_exec_path", str(configured_path))


def get_odafc_status(converter_bin: Optional[Path]) -> Tuple[bool, str]:
    configure_odafc(converter_bin)
    configured = ezdxf.options.get("odafc-addon", "unix_exec_path", "").strip()
    installed = odafc.is_installed()
    if installed:
        return True, configured or "ODAFileConverter resolved from PATH"
    if configured:
        return False, f"Configured path not usable: {configured}"
    return False, "No ODA File Converter configured or found on PATH"


def _extract_from_document(doc: ezdxf.document.Drawing, source_kind: str, notes: List[str]) -> ExtractionResult:
    msp = doc.modelspace()

    entities: List[Dict[str, str]] = []
    type_counts: Dict[str, int] = {}
    layer_counts: Dict[str, int] = {}

    all_layers = {layer.dxf.name for layer in doc.layers}

    for entity in msp:
        e_type = entity.dxftype()
        layer = getattr(entity.dxf, "layer", "0")
        handle = getattr(entity.dxf, "handle", "")
        entities.append({"handle": str(handle), "entity_type": str(e_type), "layer": str(layer)})

        type_counts[e_type] = type_counts.get(e_type, 0) + 1
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    entity_types = [{"entity_type": k, "count": str(v)} for k, v in sorted(type_counts.items())]
    entity_types.append({"entity_type": "TOTAL", "count": str(len(entities))})

    layers = []
    for layer_name in sorted(all_layers):
        layers.append({"layer": layer_name, "entity_count": str(layer_counts.get(layer_name, 0))})

    return ExtractionResult(
        entities=entities,
        layers=layers,
        entity_types=entity_types,
        source_kind=source_kind,
        notes=notes,
    )


def _resolve_executable_path(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    path = Path(os.path.expanduser(value))
    if path.is_file() and os.access(path, os.X_OK):
        return path
    if path.is_dir():
        for candidate in (
            path / "Contents" / "MacOS" / path.name,
            path / "Contents" / "MacOS" / "ODAFileConverter",
            path / "Contents" / "MacOS" / "TeighaFileConverter",
        ):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
    return None


def _find_converter_binary(preferred: Optional[Path] = None) -> Optional[Path]:
    if preferred:
        resolved_preferred = _resolve_executable_path(str(preferred))
        if resolved_preferred:
            return resolved_preferred

    env_candidates = [
        os.environ.get("DWG_CONVERTER_BIN"),
        os.environ.get("ODA_FILE_CONVERTER_BIN"),
        os.environ.get("TEIGHA_FILE_CONVERTER_BIN"),
        _read_saved_converter_path(),
    ]
    for candidate in env_candidates:
        resolved = _resolve_executable_path(candidate)
        if resolved:
            return resolved

    for name in ("dwg2dxf", "ODAFileConverter", "TeighaFileConverter"):
        located = shutil.which(name)
        if located:
            return Path(located)

    common_locations = [
        "/Applications/ODAFileConverter.app",
        "/Applications/TeighaFileConverter.app",
        "/Applications/ODA File Converter.app",
        "/usr/local/bin/dwg2dxf",
        "/opt/homebrew/bin/dwg2dxf",
    ]
    for location in common_locations:
        resolved = _resolve_executable_path(location)
        if resolved:
            return resolved

    return None


def _read_csv_dict(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        raw = f.read()
    # Backward compatibility for extractor versions that wrote literal \n.
    if "\\n" in raw:
        raw = raw.replace("\\n", "\n")
    reader = csv.DictReader(raw.splitlines())
    return list(reader)


def _default_extractor_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "libraries" / "libdxfrw" / "tools" / "dwg_entity_types"


def run_dwg_extractor(
    dwg_path: Path,
    extractor_bin: Optional[Path] = None,
    timeout_sec: int = 30,
) -> ExtractionResult:
    stage_start = time.perf_counter()
    extractor = extractor_bin or _default_extractor_path()
    if not extractor.exists():
        raise ExtractionError(
            f"DWG extractor not found at {extractor}. Build it before running the UI."
        )

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        entities_csv = tmp / "entities.csv"
        layers_csv = tmp / "layers.csv"
        types_csv = tmp / "types.csv"

        cmd = [
            str(extractor),
            str(dwg_path),
            "--entities-csv",
            str(entities_csv),
            "--layers-csv",
            str(layers_csv),
            "--types-csv",
            str(types_csv),
        ]

        try:
            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractionError(f"DWG direct extraction timed out after {timeout_sec}s") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            msg = stderr if stderr else f"dwg_entity_types exited with {proc.returncode}"
            raise ExtractionError(msg)

        if not entities_csv.exists() or not layers_csv.exists() or not types_csv.exists():
            raise ExtractionError("DWG extraction completed but expected CSV outputs were not produced")

        return ExtractionResult(
            entities=_read_csv_dict(entities_csv),
            layers=_read_csv_dict(layers_csv),
            entity_types=_read_csv_dict(types_csv),
            source_kind="dwg",
            notes=[
                "Entities and layers were read directly from DWG.",
                f"stage[dwg_entity_types]: {_elapsed_s(stage_start)}s",
            ],
        )


def _try_odafc_readfile(dwg_path: Path, converter_bin: Optional[Path]) -> ExtractionResult:
    stage_start = time.perf_counter()
    configure_odafc(converter_bin)
    if not odafc.is_installed():
        raise ExtractionError("ODA File Converter is not installed or not configured")

    try:
        doc = odafc.readfile(str(dwg_path))
    except Exception as exc:
        raise ExtractionError(f"ezdxf odafc failed: {exc}") from exc

    return _extract_from_document(
        doc,
        source_kind="dwg",
        notes=[
            "DWG loaded through ezdxf.addons.odafc (ODA File Converter bridge).",
            f"stage[odafc.readfile]: {_elapsed_s(stage_start)}s",
        ],
    )


def _try_run(cmd: List[str], cwd: Optional[Path] = None, timeout_sec: int = 90) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, (proc.stdout or "").strip()
    return False, ((proc.stderr or proc.stdout) or "").strip()


def _try_dwg2dxf(dwg_path: Path, dxf_path: Path) -> Tuple[bool, str]:
    bin_path = _find_converter_binary()
    if not bin_path:
        return False, "dwg2dxf not found"
    ok, msg = _try_run([str(bin_path), str(dwg_path), str(dxf_path)])
    if ok and dxf_path.exists():
        return True, f"Converted with {bin_path.name}"
    return False, msg


def _try_oda_file_converter(dwg_path: Path, dxf_path: Path, preferred: Optional[Path] = None) -> Tuple[bool, str]:
    oda = _find_converter_binary(preferred)
    if not oda:
        return False, "ODAFileConverter/TeighaFileConverter not found"

    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "src"
        out_dir = Path(td) / "out"
        src_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        src_copy = src_dir / dwg_path.name
        shutil.copy2(dwg_path, src_copy)

        attempts = [
            [str(oda), str(src_dir), str(out_dir), "ACAD2018", "DXF", "0", "1"],
            [str(oda), str(src_dir), str(out_dir), "ACAD2013", "DXF", "0", "1"],
            [str(oda), str(src_dir), str(out_dir), "ACAD2010", "DXF", "0", "1"],
        ]

        for cmd in attempts:
            ok, msg = _try_run(cmd, timeout_sec=120)
            if not ok:
                continue
            candidates = sorted(out_dir.rglob("*.dxf"))
            if candidates:
                shutil.copy2(candidates[0], dxf_path)
                return True, f"Converted with {Path(oda).name}"

    return False, "ODA converter executed but no DXF output found"


def convert_dwg_to_dxf(dwg_path: Path, dxf_path: Path, converter_bin: Optional[Path] = None) -> Tuple[bool, List[str]]:
    notes: List[str] = []

    s1 = time.perf_counter()
    ok, msg = _try_dwg2dxf(dwg_path, dxf_path)
    notes.append(f"dwg2dxf: {msg} ({_elapsed_s(s1)}s)")
    if ok:
        return True, notes

    s2 = time.perf_counter()
    ok, msg = _try_oda_file_converter(dwg_path, dxf_path, preferred=converter_bin)
    notes.append(f"ODA/Teigha: {msg} ({_elapsed_s(s2)}s)")
    if ok:
        return True, notes

    return False, notes


def extract_from_dxf(dxf_path: Path) -> ExtractionResult:
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:
        raise ExtractionError(f"Failed reading DXF: {exc}") from exc
    return _extract_from_document(
        doc,
        source_kind="dxf",
        notes=["DWG could not be read directly. Data was extracted from converted DXF."],
    )


def extract_entities_and_layers(
    input_path: Path,
    extractor_bin: Optional[Path] = None,
    converter_bin: Optional[Path] = None,
    timeout_sec: int = 30,
) -> ExtractionResult:
    overall_start = time.perf_counter()
    path = Path(input_path)
    ext = path.suffix.lower()

    if ext == ".dxf":
        return extract_from_dxf(path)

    if ext != ".dwg":
        raise ExtractionError(f"Unsupported file type: {ext}")

    try:
        return _try_odafc_readfile(path, converter_bin)
    except ExtractionError as odafc_error:
        odafc_note = f"{odafc_error}"
    else:
        odafc_note = ""

    try:
        result = run_dwg_extractor(path, extractor_bin=extractor_bin, timeout_sec=timeout_sec)
        if odafc_note:
            result.notes.insert(0, f"odafc attempt failed first: {odafc_note}")
        result.notes.append(f"stage[extract.total]: {_elapsed_s(overall_start)}s")
        return result
    except ExtractionError as dwg_error:
        with tempfile.TemporaryDirectory() as td:
            dxf_path = Path(td) / f"{path.stem}.dxf"
            ok, conv_notes = convert_dwg_to_dxf(path, dxf_path, converter_bin=converter_bin)
            if not ok:
                raise ExtractionError(
                    "Direct DWG extraction failed and DWG->DXF conversion failed. "
                    f"DWG error: {dwg_error}. odafc: {odafc_note}. Conversion attempts: {' | '.join(conv_notes)}"
                ) from dwg_error

            result = extract_from_dxf(dxf_path)
            result.notes.insert(0, f"DWG direct extraction failed: {dwg_error}")
            if odafc_note:
                result.notes.insert(1, f"odafc attempt failed first: {odafc_note}")
            result.notes.extend(conv_notes)
            result.notes.append(f"stage[extract.total]: {_elapsed_s(overall_start)}s")
            return result
