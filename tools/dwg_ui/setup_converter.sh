#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config_file="$repo_root/tools/dwg_ui/.converter-path"

usage() {
  cat <<'EOF'
Usage:
  tools/dwg_ui/setup_converter.sh <path-to-converter>

Examples:
  tools/dwg_ui/setup_converter.sh /Applications/ODAFileConverter.app
  tools/dwg_ui/setup_converter.sh /usr/local/bin/dwg2dxf
  tools/dwg_ui/setup_converter.sh /opt/homebrew/bin/dwg2dxf
EOF
}

resolve_path() {
  local input="$1"
  if [[ -x "$input" ]]; then
    printf '%s' "$input"
    return 0
  fi

  if [[ -d "$input" ]]; then
    for candidate in \
      "$input/Contents/MacOS/$(basename "$input")" \
      "$input/Contents/MacOS/ODAFileConverter" \
      "$input/Contents/MacOS/TeighaFileConverter"; do
      if [[ -x "$candidate" ]]; then
        printf '%s' "$candidate"
        return 0
      fi
    done
  fi

  return 1
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

resolved="$(resolve_path "$1" || true)"
if [[ -z "$resolved" ]]; then
  echo "Could not find an executable converter at: $1" >&2
  echo "Install ODA File Converter, Teigha File Converter, or a dwg2dxf binary first." >&2
  exit 2
fi

printf '%s\n' "$resolved" > "$config_file"

echo "Saved converter path to: $config_file"
echo "Converter: $resolved"
echo "Restart the Streamlit app to use it automatically."
