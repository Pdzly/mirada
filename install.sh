#!/usr/bin/env bash
# Instalador de Mirada — instala en tu usuario (~/.local), sin sudo.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPDIR="$DATA/mirada"
BINDIR="$HOME/.local/bin"
DESKDIR="$DATA/applications"
ICONDIR="$DATA/icons/hicolor/scalable/apps"

echo "==> Comprobando dependencias del sistema"
command -v python3 >/dev/null || { echo "Falta python3"; exit 1; }
python3 - <<'PY' || { echo "Mirada necesita Python 3.10 o superior"; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
python3 -c 'import venv, ensurepip' 2>/dev/null || {
  echo "Falta el módulo venv. En Debian/Ubuntu: sudo apt install python3-venv"; exit 1; }

# Se guarda la salida antes de buscar en ella: con «pipefail», «ldconfig | grep -q»
# puede fallar por SIGPIPE aunque la biblioteca exista.
LDCONFIG="$(command -v ldconfig || echo /sbin/ldconfig)"
LIBS="$("$LDCONFIG" -p 2>/dev/null || true)"
MISSING=""
grep -q 'libportaudio' <<<"$LIBS" || MISSING="$MISSING portaudio"
grep -q 'libxcb-cursor' <<<"$LIBS" || MISSING="$MISSING xcb-cursor"
if [ -n "$MISSING" ]; then
  echo "Aviso: faltan bibliotecas:$MISSING"
  echo "  Debian/Ubuntu: sudo apt install libportaudio2 libxcb-cursor0"
  echo "  Fedora:        sudo dnf install portaudio xcb-util-cursor"
  echo "  Arch:          sudo pacman -S portaudio xcb-util-cursor"
  echo "  openSUSE:      sudo zypper install libportaudio2 xcb-util-cursor"
  echo "(Sin PortAudio, Mirada funciona igual pero sin seguimiento por voz.)"
fi

echo "==> Creando entorno en $APPDIR"
mkdir -p "$APPDIR" "$BINDIR" "$DESKDIR" "$ICONDIR"
rm -rf "$APPDIR/venv"
rm -f "$APPDIR/mirada.py"   # restos de la versión 0.1
python3 -m venv "$APPDIR/venv"
"$APPDIR/venv/bin/python" -m pip install --upgrade pip -q
"$APPDIR/venv/bin/python" -m pip install -q "$SRC"

ln -sf "$APPDIR/venv/bin/mirada" "$BINDIR/mirada"
install -m 644 "$SRC/src/mirada/mirada.svg" "$ICONDIR/mirada.svg"
sed "s|^Exec=.*|Exec=$BINDIR/mirada|" "$SRC/data/mirada.desktop" > "$DESKDIR/mirada.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DESKDIR" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$DATA/icons/hicolor" 2>/dev/null || true

echo "==> Listo: $("$BINDIR/mirada" --version)"
echo "    Abre 'Mirada' desde el menú de aplicaciones o ejecuta: mirada"
case ":$PATH:" in *":$BINDIR:"*) ;; *) echo "Nota: agrega $BINDIR a tu PATH para usar el comando 'mirada'.";; esac
