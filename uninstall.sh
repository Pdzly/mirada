#!/usr/bin/env bash
# Desinstala Mirada de tu usuario. Con --purge borra también tu configuración y guion.
set -euo pipefail
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DATA/mirada"
rm -f "$HOME/.local/bin/mirada" "$DATA/applications/mirada.desktop" \
      "$DATA/icons/hicolor/scalable/apps/mirada.svg"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA/applications" || true
if [ "${1:-}" = "--purge" ]; then
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/mirada"
  echo "Mirada desinstalado (configuración y guion borrados)."
else
  echo "Mirada desinstalado. Tu configuración y guion siguen en ${XDG_CONFIG_HOME:-$HOME/.config}/mirada"
  echo "(usa --purge para borrarlos)."
fi
