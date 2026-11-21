"""Revisa que las librerias esten instaladas y las instala si faltan.

Lo usan iniciar.bat e iniciar.sh. Solo usa la libreria estandar de Python.
Sin internet no hace nada si ya esta todo instalado.
"""

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

REQUISITOS = Path(__file__).resolve().parent / "requirements.txt"


def nombres():
    for linea in REQUISITOS.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if linea:
            yield re.split(r"[<>=!~\[; ]", linea, maxsplit=1)[0]


def faltan():
    pendientes = []
    for nombre in nombres():
        try:
            metadata.version(nombre)
        except metadata.PackageNotFoundError:
            pendientes.append(nombre)
    return pendientes


def main():
    pendientes = faltan()
    if not pendientes:
        return 0
    print("Instalando librerias que faltan:", ", ".join(pendientes))
    print("La primera vez usa internet (unos 100 MB). Despues ya no hace falta.")
    comando = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUISITOS)]
    for intento in (1, 2, 3):
        if subprocess.call(comando) == 0:
            return 0
        if intento < 3:
            print(f"No se pudo descargar. Reintentando ({intento + 1} de 3)...")
    print()
    print("No se pudieron instalar las librerias. Revisa que la computadora tenga internet")
    print("y vuelve a abrir el programa. Si sigue igual, mira la seccion 'Si algo falla' del README.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
