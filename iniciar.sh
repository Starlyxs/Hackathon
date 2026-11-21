#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  BOOT=python3
elif command -v python >/dev/null 2>&1; then
  BOOT=python
else
  echo "Necesitas Python 3.11 o mas nuevo: https://www.python.org/downloads/"
  exit 1
fi

"$BOOT" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"

if [[ ! -x .venv/bin/python ]]; then
  echo "Creando el entorno local..."
  "$BOOT" -m venv .venv
fi

echo "Instalando librerias. La primera vez usa internet. Despues ya no hace falta."
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Abre http://127.0.0.1:8000"
echo "Para cerrar el programa, pulsa Ctrl+C."
echo
( sleep 3
  if command -v open >/dev/null 2>&1; then open "http://127.0.0.1:8000"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "http://127.0.0.1:8000"
  fi
) >/dev/null 2>&1 &

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
