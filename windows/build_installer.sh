#!/bin/sh
# Builds windows/dist/TASEMS-Setup-v<N>.exe on Linux. N is in windows/VERSION: raise it by 1 for every exe that
# is sent, so the newest is always the highest number (project lead, 28 Oct 2026).
# Needs: makensis, 7z, unzip, curl, pip, a Python with the project's requirements for collectstatic. Everything is downloaded from official sources:
#   Python 3.12 for Windows  - NuGet package "python" (published by the Python core team)
#   Python packages          - PyPI, Windows wheels for requirements.txt (+ waitress, the Windows web server)
#   PostgreSQL 16 for Windows - the binaries inside PyPI's "pgserver" Windows wheel
#   GTK 3 (for PDFs)         - tschoonj/GTK-for-Windows-Runtime-Environment-Installer on GitHub
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=${WORK:-/tmp/tasems-winbuild}
OUT="$ROOT/windows/dist"
PYV=3.12.10
GTK_URL=https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe
rm -rf "$WORK/build" && mkdir -p "$WORK/build" "$WORK/cache" "$OUT"
B="$WORK/build"; C="$WORK/cache"

[ -f "$C/python.nupkg" ] || curl -sSL -o "$C/python.nupkg" "https://api.nuget.org/v3-flatcontainer/python/$PYV/python.$PYV.nupkg"
[ -f "$C/gtk.exe" ] || curl -sSL -o "$C/gtk.exe" "$GTK_URL"
ls "$C"/pgserver-*win_amd64.whl >/dev/null 2>&1 || pip download -q --no-deps --only-binary=:all: \
  --platform win_amd64 --python-version 3.12 pgserver==0.1.4 -d "$C"
# The Windows build has no time zone files; they are the same on every platform, so take them from the Linux
# build of the same PostgreSQL (16.2). Without them PostgreSQL refuses TimeZone "UTC".
ls "$C"/pgserver-*manylinux*.whl >/dev/null 2>&1 || pip download -q --no-deps --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 3.12 pgserver==0.1.4 -d "$C"

echo "Python..."
mkdir -p "$WORK/py" && unzip -q -o "$C/python.nupkg" 'tools/*' -d "$WORK/py"
mv "$WORK/py/tools" "$B/python" && rm -rf "$WORK/py"
grep -v '^gunicorn' "$ROOT/requirements.txt" > "$WORK/req-win.txt"
# pip decides "only on Windows / only before Python 3.13" by the computer it runs on, so name them here.
printf 'waitress==3.0.2\ntzdata\ntyping-extensions>=4.6\ncolorama\n' >> "$WORK/req-win.txt"
pip install -q --target "$B/python/Lib/site-packages" --platform win_amd64 --python-version 3.12 \
  --implementation cp --only-binary=:all: -r "$WORK/req-win.txt"

echo "PostgreSQL..."
mkdir -p "$WORK/pg" && unzip -q -o "$C"/pgserver-*win_amd64.whl 'pgserver/pginstall/*' -d "$WORK/pg"
mkdir -p "$B/pgsql" && for d in bin lib share; do mv "$WORK/pg/pgserver/pginstall/$d" "$B/pgsql/"; done
rm -rf "$WORK/pg" && mkdir -p "$WORK/pg"
unzip -q -o "$C"/pgserver-*manylinux*.whl 'pgserver/pginstall/share/postgresql/timezone/*' -d "$WORK/pg"
mv "$WORK/pg/pgserver/pginstall/share/postgresql/timezone" "$B/pgsql/share/postgresql/timezone"
rm -rf "$WORK/pg"
test -f "$B/pgsql/share/postgresql/timezone/UTC"

echo "GTK..."
rm -rf "$WORK/gtk" && 7z x -y -o"$WORK/gtk" "$C/gtk.exe" >/dev/null
mkdir -p "$B/gtk" && mv "$WORK/gtk/\$_63_" "$B/gtk/bin" && mv "$WORK/gtk/etc" "$B/gtk/etc" && mv "$WORK/gtk/lib" "$B/gtk/lib"
rm -rf "$WORK/gtk"

echo "TASEMS..."
mkdir -p "$B/app" && (cd "$ROOT" && git archive HEAD) | tar -x -C "$B/app"
mkdir -p "$B/app/windows" && cp "$ROOT/windows/launcher.py" "$B/app/windows/launcher.py"   # the working copy, in case it is not committed yet
rm -rf "$B/app/tests" "$B/app/screenshots-m3" "$B/app/offline" "$B/app/windows/dist" "$B/app/docs/reference"
(cd "$B/app" && SECRET_KEY=build FIELD_ENCRYPTION_KEY=Y2ktb25seS1ub3Qtc2VjcmV0LWtleS0zMmJ5dGVzISE= \
  DATABASE_URL=postgres://x@localhost/x python manage.py collectstatic --noinput -v0)
python - "$ROOT/static/img/arqam-logo-512.png" "$B/app/windows/tasems.ico" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert("RGBA").save(sys.argv[2], sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
PY
find "$B" -name "__pycache__" -type d -prune -exec rm -rf {} +

VERSION=$(tr -d " \r\n" < "$ROOT/windows/VERSION")
rm -f "$OUT"/TASEMS-Setup*.exe
echo "Installer..."
makensis -V2 -DBUILD="$B" -DOUTDIR="$OUT" -DVERSION="$VERSION" "$ROOT/windows/installer.nsi"
ls -la "$OUT/TASEMS-Setup-v$VERSION.exe"
