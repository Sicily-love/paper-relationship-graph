#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h:h}"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
APP="$ROOT/Paper Atlas.app"
DIST="$ROOT/dist"
STAGING="${TMPDIR:-/tmp}/paper-atlas-dmg-$VERSION"
DMG="$DIST/Paper-Atlas-$VERSION.dmg"
SIGN_IDENTITY="${PAPER_ATLAS_SIGN_IDENTITY:--}"

"$ROOT/platform/macos/build_app.sh"
rm -rf "$STAGING"
mkdir -p "$STAGING" "$DIST"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
rm -f "$DMG"
hdiutil create -volname "Paper Atlas" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
rm -rf "$STAGING"

if [[ "$SIGN_IDENTITY" != "-" ]]; then
  codesign --force --sign "$SIGN_IDENTITY" "$DMG"
fi

if [[ -n "${PAPER_ATLAS_NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$PAPER_ATLAS_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi

shasum -a 256 "$DMG" > "$DMG.sha256"
echo "Paper Atlas $VERSION 发布包：$DMG"
