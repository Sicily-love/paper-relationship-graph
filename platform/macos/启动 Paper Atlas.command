#!/bin/zsh
set -e
cd "${0:A:h:h:h}"
exec python3 scripts/start_app.py
