#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out="$repo_root/dist"
if [[ $# -eq 2 && $1 == --out && -n $2 ]]; then
    out=$2
elif [[ $# -ne 0 ]]; then
    echo "Usage: ${0##*/} [--out DIR]" >&2
    exit 2
fi

if [[ $(dpkg --print-architecture) != amd64 ]]; then
    echo "This AppImage requires an amd64 build environment." >&2
    exit 1
fi

mkdir -p -- "$out"
out=$(cd -- "$out" && pwd)
work=$(mktemp -d "$out/.mirada-appimage.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
appdir=$work/Mirada.AppDir

"$repo_root/packaging/build-runtime.sh" "$appdir/usr"
python=$appdir/usr/python/bin/python3
version=$("$python" -IB -c 'from mirada import __version__; print(__version__)')
site_packages=$("$python" -IB -c 'import sysconfig; print(sysconfig.get_path("purelib"))')

install -m755 -- "$repo_root/packaging/appimage/AppRun" "$appdir/AppRun"
install -m644 -- "$repo_root/packaging/appimage/sitecustomize.py" "$site_packages/sitecustomize.py"
install -m644 -- "$repo_root/data/mirada.desktop" "$appdir/mirada.desktop"
install -m644 -- "$repo_root/src/mirada/mirada.svg" "$appdir/mirada.svg"
ln -s mirada.svg "$appdir/.DirIcon"

config=$repo_root/packaging/appimage
mkdir -- "$work/apt" "$work/native"
mapfile -t packages < <(cut -d ' ' -f 1 "$config/libraries.txt" "$config/fallback-libraries.txt")
(cd -- "$work/apt" && apt-get download "${packages[@]}")
for archive in "$work/apt/"*.deb; do
    dpkg-deb --extract "$archive" "$work/native"
done

copy_libraries() {
    local manifest=$1 destination=$2 package library source
    local -a entry
    while read -r -a entry; do
        package=${entry[0]}
        for library in "${entry[@]:1}"; do
            source=$work/native/usr/lib/x86_64-linux-gnu/$library
            if [[ ! -f "$source" ]]; then
                source=$work/native/lib/x86_64-linux-gnu/$library
            fi
            install -Dm644 -- "$source" "$destination/$library"
        done
        install -Dm644 -- "$work/native/usr/share/doc/$package/copyright" \
            "$appdir/usr/share/doc/$package/copyright"
    done < "$manifest"
}

copy_libraries "$config/libraries.txt" "$appdir/usr/lib"
copy_libraries "$config/fallback-libraries.txt" "$appdir/usr/lib/fallback"
install -Dm644 -- "$repo_root/LICENSE" "$appdir/usr/share/doc/mirada/copyright"

tool_url=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
tool_sha256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
runtime_url=https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64
runtime_sha256=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d

download_verified() {
    local url=$1 expected=$2 destination=$3
    "$python" -ISB - "$url" "$destination" <<'PY'
from shutil import copyfileobj
from sys import argv
from urllib.request import urlopen

with urlopen(argv[1], timeout=60) as response, open(argv[2], "wb") as target:
    copyfileobj(response, target)
PY
    printf '%s  %s\n' "$expected" "$destination" | sha256sum --check --status
}

tool=$work/appimagetool
runtime=$work/runtime-x86_64
download_verified "$tool_url" "$tool_sha256" "$tool"
download_verified "$runtime_url" "$runtime_sha256" "$runtime"
chmod +x -- "$tool"
artifact=Mirada-${version}-x86_64.AppImage
ARCH=x86_64 "$tool" --appimage-extract-and-run --no-appstream --runtime-file "$runtime" \
    --mksquashfs-opt=-processors --mksquashfs-opt=2 "$appdir" "$work/$artifact"
mv -Tf -- "$work/$artifact" "$out/$artifact"
echo "$out/$artifact"
