#!/usr/bin/env bash
# Testet das Mirada-AppImage in Containern ohne Python/Qt.
# Aufruf: packaging/test/test-appimage.sh <pfad-zur.AppImage> [image...]
set -uo pipefail

DEFAULT_IMAGES=(debian:12-slim ubuntu:22.04 ubuntu:24.04)

if [ $# -lt 1 ] || [ ! -f "$1" ]; then
  echo "Aufruf: $0 <pfad-zur.AppImage> [image...]" >&2
  exit 2
fi
APPIMAGE="$(realpath "$1")"
shift
if [ $# -gt 0 ]; then IMAGES=("$@"); else IMAGES=("${DEFAULT_IMAGES[@]}"); fi

read -r -d '' INNER <<'INNER_EOF' || true
set -u
export DEBIAN_FRONTEND=noninteractive
fail() { echo "FAILED-STEP: $*"; exit 1; }
step() { echo "--- $*"; }

step "Kein Python/Qt im Container"
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  fail "python ist im Testcontainer vorhanden, Test waere aussagelos"
fi
if ldconfig -p 2>/dev/null | grep -qE 'libxcb-cursor|libQt6|libportaudio'; then
  fail "libxcb-cursor/Qt6/portaudio liegen im Container, Test waere aussagelos"
fi
echo "ok: weder python3 noch xcb-cursor/Qt6/portaudio vorhanden"

# Testcontainer-Werkzeuge (nicht Teil der App): kein FUSE noetig dank extract-and-run.
# xvfb zieht X-Server-Libs nach, aber ausdruecklich NICHT libxcb-cursor0 und kein python.
step "Testwerkzeuge installieren (xvfb, xauth)"
apt-get update -qq >/dev/null 2>&1 || fail "apt-get update"
apt-get install -y -qq --no-install-recommends xvfb xauth >/tmp/install.log 2>&1 || { tail -20 /tmp/install.log; fail "Testwerkzeuge"; }
command -v python3 >/dev/null 2>&1 && fail "python3 wurde durch Testwerkzeuge nachinstalliert"
dpkg -s libxcb-cursor0 >/dev/null 2>&1 && fail "libxcb-cursor0 wurde nachinstalliert"
echo "ok: Testwerkzeuge installiert, kein python3, kein libxcb-cursor0"

# Das AppImage wird als normaler Benutzer ausgefuehrt (manche Runtimes
# verweigern root) und aus einer Kopie, damit das Mount-Volume schreibgeschuetzt bleiben kann.
useradd -m tester >/dev/null 2>&1 || fail "useradd"
cp /pkg/app.AppImage /home/tester/app.AppImage
chmod +x /home/tester/app.AppImage
chown tester /home/tester/app.AppImage

as_tester() { su tester -s /bin/bash -c "cd /home/tester && $*"; }

step "--appimage-extract-and-run --version"
OUT="$(as_tester "./app.AppImage --appimage-extract-and-run --version" 2>&1)" || fail "--version Exit != 0: $OUT"
echo "$OUT"
case "$OUT" in *"mirada "[0-9]*) ;; *) fail "unerwartete Versionsausgabe: $OUT" ;; esac

check_run() { # <label> <env-praefix> <befehl nach cd>
  local label="$1" envp="$2" cmd="$3"
  as_tester "$envp timeout 10 $cmd" >/tmp/run.log 2>&1
  local rc=$?
  cat /tmp/run.log
  [ "$rc" -eq 124 ] || fail "$label: Exit $rc (erwartet 124 = lief bis timeout)"
  if grep -qiE 'Traceback|could not load the Qt platform plugin|Aborted|core dumped|Segmentation|error while loading shared libraries' /tmp/run.log; then
    fail "$label: Traceback/Plattform-Plugin-/Bibliotheksfehler im Log"
  fi
  echo "OK: $label"
}

step "Fensterstart offscreen"
check_run "offscreen --start" "QT_QPA_PLATFORM=offscreen" "./app.AppImage --appimage-extract-and-run --start"

step "Fensterstart xcb unter Xvfb (libxcb-cursor muss gebuendelt sein)"
check_run "xcb --start (xvfb)" "QT_QPA_PLATFORM=xcb" \
  "xvfb-run -a -s '-screen 0 1280x800x24' ./app.AppImage --appimage-extract-and-run --start"

step "PortAudio: gebuendelt und ladbar, oder App startet sauber ohne Sprachsteuerung"
as_tester "./app.AppImage --appimage-extract" >/dev/null 2>&1 || fail "--appimage-extract"
PA="$(find /home/tester/squashfs-root -name 'libportaudio.so*' 2>/dev/null | head -n1)"
if [ -n "$PA" ]; then
  echo "gebuendelt: $PA"
  MISSING="$(LD_LIBRARY_PATH="$(dirname "$PA")" ldd "$PA" 2>&1 | grep 'not found' || true)"
  if [ -n "$MISSING" ]; then
    echo "$MISSING"
    echo "WARNUNG: portaudio hat ungeloeste Abhaengigkeiten (z. B. ALSA/JACK); Start ohne Sprachsteuerung muss sauber sein (oben geprueft)"
  else
    echo "ok: libportaudio und Abhaengigkeiten aufloesbar"
  fi
else
  echo "libportaudio nicht im AppImage gefunden"
  fail "portaudio nicht gebuendelt"
fi
echo "ALL-OK"
INNER_EOF

overall=0
declare -A RESULT
for img in "${IMAGES[@]}"; do
  echo "=================== $img ==================="
  if ! docker pull -q "$img" >/dev/null 2>&1 && ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "SKIP: Image $img nicht verfuegbar"
    RESULT[$img]="SKIP"
    continue
  fi
  log="$(mktemp)"
  docker run --rm -v "$APPIMAGE:/pkg/app.AppImage:ro" "$img" bash -c "$INNER" 2>&1 | tee "$log"
  if grep -q '^ALL-OK$' "$log"; then
    RESULT[$img]="PASS"
  else
    RESULT[$img]="FAIL"
    overall=1
  fi
  rm -f "$log"
done

echo
echo "=================== Ergebnis (AppImage: $(basename "$APPIMAGE")) ==================="
for img in "${IMAGES[@]}"; do printf '%-6s %s\n' "${RESULT[$img]}" "$img"; done
passed=0
for img in "${IMAGES[@]}"; do [ "${RESULT[$img]}" = PASS ] && passed=$((passed + 1)); done
[ "$passed" -gt 0 ] || { echo "Kein Image getestet"; exit 1; }
exit "$overall"
