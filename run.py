"""Arranque para la laptop del maestro y para el ejecutable."""

import os
import threading
import webbrowser

import uvicorn

from app.main import app


def main():
    port = int(os.environ.get("HOJAS_PORT", "8000"))
    url = f"http://127.0.0.1:{port}"

    def open_browser():
        webbrowser.open(url)

    threading.Timer(1.2, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
