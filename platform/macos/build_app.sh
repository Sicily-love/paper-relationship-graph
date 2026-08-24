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
PYTHON_RUNTIME="$APP/Contents/Resources/python"
SIGN_IDENTITY="${PAPER_ATLAS_SIGN_IDENTITY:--}"
if [[ -n "${PAPER_ATLAS_BUILD_PYTHON:-}" ]]; then
  BUILD_PYTHON="$PAPER_ATLAS_BUILD_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  BUILD_PYTHON="$ROOT/.venv/bin/python"
else
  BUILD_PYTHON="python3"
fi
EMBED_PYTHON="${PAPER_ATLAS_EMBED_PYTHON:-1}"
PYTHON_RUNTIME_SOURCE="${PAPER_ATLAS_PYTHON_RUNTIME_SOURCE:-}"
PYTHON_RUNTIME_LABEL="${PAPER_ATLAS_PYTHON_RUNTIME_LABEL:-Python.org macOS universal2}"

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$CACHE"
"$BUILD_PYTHON" "$ROOT/scripts/generate_release_notes.py"
cp "$ROOT/platform/macos/Info.plist" "$APP/Contents/Info.plist"
rm -rf "$RUNTIME"
mkdir -p "$RUNTIME"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$ROOT/scripts" "$RUNTIME/"
rsync -a "$ROOT/web" "$RUNTIME/"
rsync -a "$ROOT/config" "$RUNTIME/"
cp "$ROOT/requirements.txt" "$ROOT/VERSION" "$RUNTIME/"
"$BUILD_PYTHON" "$ROOT/scripts/prepare_release_seed.py" "$RUNTIME"

if [[ "$EMBED_PYTHON" == "1" ]]; then
  if [[ -z "$PYTHON_RUNTIME_SOURCE" ]]; then
    PYTHON_RUNTIME_SOURCE="$ROOT/.cache/python-runtime/Python.framework/Versions/3.12"
    if [[ ! -d "$PYTHON_RUNTIME_SOURCE" ]]; then
      "$ROOT/platform/macos/prepare_python_runtime.sh"
    fi
  fi
  if [[ ! -d "$PYTHON_RUNTIME_SOURCE" ]]; then
    echo "缺少可嵌入 Python：$PYTHON_RUNTIME_SOURCE" >&2
    exit 2
  fi
  "$BUILD_PYTHON" "$ROOT/scripts/embed_python_runtime.py" \
    --source "$PYTHON_RUNTIME_SOURCE" \
    --destination "$PYTHON_RUNTIME" \
    --package-python "$BUILD_PYTHON" \
    --source-label "$PYTHON_RUNTIME_LABEL"
else
  rm -rf "$PYTHON_RUNTIME"
fi

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

if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --deep --options runtime --sign - "$APP"
else
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP"
fi
codesign --verify --deep --strict "$APP"

# Refresh Launch Services so Stage Manager and Finder do not retain an icon
# from an earlier build with the same bundle identifier.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$APP" >/dev/null 2>&1 || true
fi
touch "$APP"

echo "Paper Atlas.app 已生成。"
