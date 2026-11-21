"""Arranque para la laptop del maestro y para el ejecutable.

- Si el programa ya esta abierto, solo abre el navegador.
- Si el puerto 8000 lo usa otra cosa, prueba con el siguiente.
"""

import os
import socket
import threading
import urllib.request
import webbrowser

import uvicorn

from app.main import app

PUERTO_BASE = int(os.environ.get("HOJAS_PORT", "8000"))


def ocupado(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def es_nuestro(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/estado", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def elegir_puerto():
    for port in range(PUERTO_BASE, PUERTO_BASE + 20):
        if not ocupado(port):
            return port, False
        if es_nuestro(port):
            return port, True
    raise SystemExit("No encontre un puerto libre entre 8000 y 8019. Cierra otros programas e intenta de nuevo.")


def main():
    port, ya_abierto = elegir_puerto()
    url = f"http://127.0.0.1:{port}"
    if ya_abierto:
        print(f"El programa ya estaba abierto. Abriendo {url}")
        webbrowser.open(url)
        return

    print()
    print(f"  EduScan esta listo en {url}")
    print("  Si el navegador no se abre solo, copia esa direccion en Chrome, Edge o Firefox.")
    print("  Para cerrar el programa, cierra esta ventana.")
    print()
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
