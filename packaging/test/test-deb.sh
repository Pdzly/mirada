#!/usr/bin/env bash
# Testet das Mirada-.deb in frischen Docker-Containern.
# Aufruf: packaging/test/test-deb.sh <pfad-zur.deb> [image...]
set -uo pipefail

DEFAULT_IMAGES=(debian:12 ubuntu:22.04 ubuntu:24.04 debian:13)

if [ $# -lt 1 ] || [ ! -f "$1" ]; then
  echo "Aufruf: $0 <pfad-zur.deb> [image...]" >&2
  exit 2
fi
DEB="$(realpath "$1")"
shift
if [ $# -gt 0 ]; then IMAGES=("$@"); else IMAGES=("${DEFAULT_IMAGES[@]}"); fi

# Skript, das im Container laeuft. Es bekommt das .deb unter /pkg/mirada.deb.
read -r -d '' INNER <<'INNER_EOF' || true
set -u
export DEBIAN_FRONTEND=noninteractive
fail() { echo "FAILED-STEP: $*"; exit 1; }
step() { echo "--- $*"; }

# Minimales Image: nur das .deb, keine vorinstallierten Zusatzpakete.
step "apt-get update + install ./mirada.deb"
apt-get update -qq >/dev/null 2>&1 || fail "apt-get update"
cp /pkg/mirada.deb /tmp/mirada.deb
apt-get install -y -qq /tmp/mirada.deb >/tmp/install.log 2>&1 || { tail -30 /tmp/install.log; fail "apt-get install"; }

step "mirada --version"
OUT="$(mirada --version 2>&1)" || fail "mirada --version Exit != 0: $OUT"
echo "$OUT"
case "$OUT" in "mirada "[0-9]*) ;; *) fail "unerwartete Versionsausgabe: $OUT" ;; esac

step "Dateien vorhanden"
[ -x /usr/bin/mirada ] || fail "/usr/bin/mirada fehlt"
[ -d /opt/mirada ] || fail "/opt/mirada fehlt"
[ -f /usr/share/applications/mirada.desktop ] || fail "mirada.desktop fehlt"
ICON="$(find /usr/share/icons /usr/share/pixmaps -name 'mirada.*' 2>/dev/null | head -n1)"
[ -n "$ICON" ] || fail "Icon unter /usr/share/icons|pixmaps fehlt"
echo "Icon: $ICON"

step "desktop-file-validate"
apt-get install -y -qq desktop-file-utils >/dev/null 2>&1 || fail "desktop-file-utils Installation"
desktop-file-validate /usr/share/applications/mirada.desktop || fail "desktop-file-validate"

# Fensterstart: Exit 124 (timeout) = App lief durchgehend. Alles andere, Traceback
# oder Plattform-Plugin-Fehler = Fehlschlag.
check_run() { # <label> <befehl...>
  local label="$1"; shift
  timeout 8 "$@" >/tmp/run.log 2>&1
  local rc=$?
  cat /tmp/run.log
  [ "$rc" -eq 124 ] || fail "$label: Exit $rc (erwartet 124 = lief bis timeout)"
  if grep -qiE 'Traceback|could not load the Qt platform plugin|Aborted|core dumped|Segmentation' /tmp/run.log; then
    fail "$label: Traceback/Plattform-Plugin-Fehler im Log"
  fi
  echo "OK: $label"
}

step "Fensterstart offscreen"
QT_QPA_PLATFORM=offscreen HOME=/tmp/h1 check_run "offscreen --start" mirada --start

step "Fensterstart xcb unter xvfb (testet libxcb-cursor)"
apt-get install -y -qq xvfb >/dev/null 2>&1 || fail "xvfb Installation"
mkdir -p /tmp/h2
QT_QPA_PLATFORM=xcb HOME=/tmp/h2 check_run "xcb --start (xvfb)" \
  xvfb-run -a -s "-screen 0 1280x800x24" mirada --start

step "apt-get purge mirada"
apt-get purge -y -qq mirada >/tmp/purge.log 2>&1 || { tail -20 /tmp/purge.log; fail "apt-get purge"; }
[ ! -e /opt/mirada ] || fail "/opt/mirada nach purge noch vorhanden"
[ ! -e /usr/bin/mirada ] || fail "/usr/bin/mirada nach purge noch vorhanden"
[ ! -e /usr/share/applications/mirada.desktop ] || fail ".desktop nach purge noch vorhanden"
LEFT="$(find /usr/share/icons /usr/share/pixmaps -name 'mirada.*' 2>/dev/null)"
[ -z "$LEFT" ] || fail "Icon nach purge noch vorhanden: $LEFT"
dpkg -s mirada >/dev/null 2>&1 && fail "dpkg kennt mirada nach purge noch"
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
  docker run --rm -v "$DEB:/pkg/mirada.deb:ro" "$img" bash -c "$INNER" 2>&1 | tee "$log"
  if grep -q '^ALL-OK$' "$log"; then
    RESULT[$img]="PASS"
  else
    RESULT[$img]="FAIL"
    overall=1
  fi
  rm -f "$log"
done

echo
echo "=================== Ergebnis (.deb: $(basename "$DEB")) ==================="
for img in "${IMAGES[@]}"; do printf '%-6s %s\n' "${RESULT[$img]}" "$img"; done
passed=0
for img in "${IMAGES[@]}"; do [ "${RESULT[$img]}" = PASS ] && passed=$((passed + 1)); done
[ "$passed" -gt 0 ] || { echo "Kein Image getestet"; exit 1; }
exit "$overall"
