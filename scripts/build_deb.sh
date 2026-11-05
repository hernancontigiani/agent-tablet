#!/usr/bin/env bash
# Build a Debian package: dist/agent-tablet_<version>_all.deb
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="agent-tablet"
APP_ID="io.github.hernancontigiani.AgentTablet"
VERSION="$(grep -m1 '^version' "$ROOT/pyproject.toml" | cut -d'"' -f2)"
BUILD="$ROOT/dist/deb-build"

rm -rf "$BUILD"
mkdir -p "$ROOT/dist"

# -- python package -----------------------------------------------------------
SITE="$BUILD/usr/lib/python3/dist-packages/agent_tablet"
mkdir -p "$SITE"
cp "$ROOT"/agent_tablet/*.py "$SITE/"
if [ -d "$ROOT/agent_tablet/locale" ]; then
  cp -r "$ROOT/agent_tablet/locale" "$SITE/"
fi

# -- executable ---------------------------------------------------------------
mkdir -p "$BUILD/usr/bin"
cat > "$BUILD/usr/bin/$PKG" <<'EOF'
#!/usr/bin/python3
import sys

from agent_tablet.app import main

sys.exit(main())
EOF
chmod 755 "$BUILD/usr/bin/$PKG"

# -- desktop file / icon / metainfo --------------------------------------------
mkdir -p "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/icons/hicolor/scalable/apps" \
         "$BUILD/usr/share/icons/hicolor/scalable/actions" \
         "$BUILD/usr/share/metainfo" \
         "$BUILD/usr/share/doc/$PKG"
# system-wide desktop entry: binary on PATH, no hardcoded working directory
sed -e "s|^Exec=.*|Exec=$PKG|" -e "/^Path=/d" \
    "$ROOT/data/$APP_ID.desktop" > "$BUILD/usr/share/applications/$APP_ID.desktop"
cp "$ROOT/data/icons/$APP_ID.svg" "$BUILD/usr/share/icons/hicolor/scalable/apps/"
cp "$ROOT/data/icons/hicolor/scalable/actions/"*.svg \
    "$BUILD/usr/share/icons/hicolor/scalable/actions/"
cp "$ROOT/data/$APP_ID.metainfo.xml" "$BUILD/usr/share/metainfo/"
cp "$ROOT/LICENSE" "$BUILD/usr/share/doc/$PKG/copyright"

# -- control ------------------------------------------------------------------
mkdir -p "$BUILD/DEBIAN"
INSTALLED_SIZE="$(du -sk "$BUILD" --exclude=DEBIAN | cut -f1)"
cat > "$BUILD/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-vte-3.91
Recommends: gir1.2-glib-2.0
Installed-Size: $INSTALLED_SIZE
Maintainer: Hernan Contigiani <hernan4790@gmail.com>
Homepage: https://github.com/hernancontigiani/agent-tablet
Description: Manage and resume AI coding agent sessions (GTK4 GUI)
 Native GTK4/libadwaita desktop app for AI coding-agent CLIs such as Claude
 Code and Cursor: browse all sessions grouped by project, name and star them,
 and resume any session in embedded terminal tabs. Unofficial community tool;
 the agents' own session data is never modified.
EOF

dpkg-deb --build --root-owner-group "$BUILD" "$ROOT/dist/${PKG}_${VERSION}_all.deb"
rm -rf "$BUILD"
echo "Built: dist/${PKG}_${VERSION}_all.deb"
