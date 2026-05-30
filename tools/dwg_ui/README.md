# DWG Wrapper UI

This UI lets you upload a DWG (or DXF) file and view:
- entities
- layers
- entity type counts

If direct DWG extraction fails, the app attempts DWG to DXF conversion and then extracts from DXF.

## Converter Setup

The app can use one of these converters if you install it locally:
- `dwg2dxf`
- `ODAFileConverter`
- `TeighaFileConverter`

The DWG fallback now also uses `ezdxf.addons.odafc`, which is the ezdxf bridge to an installed ODA File Converter.

If the binary is not on your `PATH`, you can point the UI at it with the sidebar field or save it once with:

```bash
tools/dwg_ui/setup_converter.sh /path/to/converter
```

On this Mac there is no Homebrew package for a DWG converter, so the converter must be installed manually and then pointed to by path.

## How It Works

1. Tries direct DWG extraction using:
- `libraries/libdxfrw/tools/dwg_entity_types`

2. If DWG extraction fails, tries conversion in this order:
- `dwg2dxf`
- `ODAFileConverter` or `TeighaFileConverter`

3. Extracts entities and layers from DXF with `ezdxf`.

The DWG path first tries `ezdxf.addons.odafc.readfile(...)` and only falls back to the older local DWG extractor if needed.

## Setup

From repo root:

```bash
python3 -m pip install --user -r tools/dwg_ui/requirements.txt
```

Build DWG extractor (once):

```bash
cd libraries/libdxfrw
clang++ -std=c++14 -O2 -I src -I src/intern src/intern/*.cpp src/*.cpp tools/dwg_entity_types.cpp -o tools/dwg_entity_types
```

## Run

From repo root:

```bash
streamlit run tools/dwg_ui/app.py
```

Then open the local URL shown by Streamlit and upload your file.

If you configured a converter with `setup_converter.sh`, restart the app so it picks up the saved path.
