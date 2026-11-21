#!/usr/bin/env bash
# Abre Nexam en Mac o Linux. Uso: bash iniciar.sh
set -u
cd "$(dirname "$0")/programa" || { echo "No encuentro la carpeta 'programa'."; exit 1; }

BOOT=""
for candidato in python3.11 python3.12 python3.13 python3 python; do
  if command -v "$candidato" >/dev/null 2>&1 &&
     "$candidato" -c "import sys; raise SystemExit(0 if (3,11)<=sys.version_info[:2]<=(3,13) else 1)" >/dev/null 2>&1; then
    BOOT="$candidato"
    break
  fi
done

if [[ -z "$BOOT" ]]; then
  echo "Necesitas Python 3.11, 3.12 o 3.13 y no lo encuentro."
  echo
  case "$(uname -s)" in
    Darwin) echo "Mac: instalalo desde https://www.python.org/downloads/ o con 'brew install python@3.12'." ;;
    *)      echo "Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
            echo "Fedora: sudo dnf install python3"
            echo "O desde https://www.python.org/downloads/" ;;
  esac
  echo "Despues vuelve a ejecutar: bash iniciar.sh"
  exit 1
fi

VENV="$HOME/.hojas-en-papel/venv"
VPY="$VENV/bin/python"

# Si copiaron la carpeta desde otra computadora o cambio Python, el entorno se rehace solo.
if [[ -e "$VPY" ]] && ! "$VPY" -c "import sys" >/dev/null 2>&1; then
  rm -rf "$VENV"
fi
if [[ ! -x "$VPY" ]]; then
  echo "Preparando el programa por primera vez..."
  mkdir -p "$(dirname "$VENV")"
  if ! "$BOOT" -m venv "$VENV"; then
    echo
    echo "No se pudo crear el entorno. En Ubuntu/Debian prueba: sudo apt install python3-venv python3-pip"
    exit 1
  fi
fi

"$VPY" preparar.py || { echo; echo "No se pudo preparar el programa. Mira 'Si algo falla' en el README."; exit 1; }

exec "$VPY" run.py
