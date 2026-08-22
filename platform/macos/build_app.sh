#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h:h}"
SOURCE="$ROOT/platform/macos/PaperAtlasLauncher.m"
APP="$ROOT/Paper Atlas.app"
EXECUTABLE="$APP/Contents/MacOS/Paper Atlas"
CACHE="${TMPDIR:-/tmp}/paper-atlas-clang-cache"
ICON_SOURCE="$ROOT/assets/paper-atlas-icon.png"
ICON_MASTER="$CACHE/paper-atlas-icon-1024.png"
ICON_PREPARER="$CACHE/PrepareIcon"
RUNTIME="$APP/Contents/Resources/runtime"
SIGN_IDENTITY="${PAPER_ATLAS_SIGN_IDENTITY:--}"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$CACHE"
cp "$ROOT/platform/macos/Info.plist" "$APP/Contents/Info.plist"
rm -rf "$RUNTIME"
mkdir -p "$RUNTIME"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$ROOT/scripts" "$RUNTIME/"
rsync -a "$ROOT/web" "$RUNTIME/"
rsync -a "$ROOT/config" "$RUNTIME/"
cp "$ROOT/requirements.txt" "$ROOT/VERSION" "$RUNTIME/"

CLANG_MODULE_CACHE_PATH="$CACHE" xcrun clang \
  -fobjc-arc \
  -framework Cocoa \
  -framework WebKit \
  -mmacosx-version-min=10.15 \
  -arch arm64 \
  -arch x86_64 \
  -o "$EXECUTABLE" \
  "$SOURCE"

chmod 755 "$EXECUTABLE"

CLANG_MODULE_CACHE_PATH="$CACHE" xcrun clang \
  -fobjc-arc \
  -framework AppKit \
  -o "$ICON_PREPARER" \
  "$ROOT/platform/macos/PrepareIcon.m"
"$ICON_PREPARER" \
  "$ICON_SOURCE" \
  "$ICON_MASTER" \
  "$APP/Contents/Resources/AppIcon.icns"
cp "$ICON_MASTER" "$APP/Contents/Resources/AppIcon.png"

codesign --force --deep --options runtime --sign "$SIGN_IDENTITY" "$APP"
codesign --verify --deep --strict "$APP"

# Refresh Launch Services so Stage Manager and Finder do not retain an icon
# from an earlier build with the same bundle identifier.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$APP" >/dev/null 2>&1 || true
fi
touch "$APP"

echo "Paper Atlas.app 已生成。"
