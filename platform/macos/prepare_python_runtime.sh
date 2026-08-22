#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h:h}"
VERSION="3.12.10"
CACHE="$ROOT/.cache/python-runtime"
PACKAGE="$CACHE/python-$VERSION-macos11.pkg"
EXPANDED="$CACHE/expanded-$VERSION"
FRAMEWORK="$CACHE/Python.framework"
URL="https://www.python.org/ftp/python/$VERSION/python-$VERSION-macos11.pkg"

mkdir -p "$CACHE"
if [[ ! -f "$PACKAGE" ]]; then
  curl -fL --retry 3 -o "$PACKAGE" "$URL"
elif ! pkgutil --check-signature "$PACKAGE" >/dev/null 2>&1; then
  curl -fL -C - --retry 3 -o "$PACKAGE" "$URL"
fi
pkgutil --check-signature "$PACKAGE"

if [[ ! -d "$FRAMEWORK/Versions/3.12" ]]; then
  rm -rf "$EXPANDED" "$FRAMEWORK"
  pkgutil --expand-full "$PACKAGE" "$EXPANDED"
  SOURCE="$EXPANDED/Python_Framework.pkg/Payload"
  if [[ ! -d "$SOURCE/Versions/3.12" ]]; then
    echo "Python.org 安装包中没有找到 Python.framework。" >&2
    exit 2
  fi
  cp -R "$SOURCE" "$FRAMEWORK"
  rm -rf "$EXPANDED"
fi

ARCHITECTURES="$(lipo -archs "$FRAMEWORK/Versions/3.12/bin/python3")"
if [[ "$ARCHITECTURES" != *arm64* || "$ARCHITECTURES" != *x86_64* ]]; then
  echo "Python.org 运行时不是 Intel 与 Apple Silicon 通用版本。" >&2
  exit 2
fi
echo "Python.org runtime $VERSION ($ARCHITECTURES)"
