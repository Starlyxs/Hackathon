"""Toma las capturas del tutorial con datos de ejemplo (nunca toca tus datos reales).

Uso:
    pip install playwright                      (solo para esta herramienta)
    python herramientas/capturar_tutorial.py CARPETA_DE_SALIDA
    python herramientas/crear_tutorial.py CARPETA_DE_SALIDA/capturas

Usa la misma prueba simulada del botón de Inicio (app/demo.py), enciende el programa en el puerto 8765 con
esa base temporal, sube un PDF escaneado de ejemplo y fotografía cada pantalla (1280x720).
Necesita Microsoft Edge o Google Chrome instalado.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PORT = 8765


def seed(base):
    """Crea la prueba simulada del programa en una base temporal. Debe correr antes de importar la app."""
    data = base / "datos"
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    os.environ["EDU_STORE"] = str(data / "store.json")
    os.environ["EDU_SHEETS"] = str(data / "sheets")

    from app.demo import SCHOOL_GROUP, simulate_school

    status = simulate_school()
    shutil.copy(data / "sheets" / "demo" / "entrega-demo.pdf", base / "entrega.pdf")
    shutil.copy(data / "sheets" / "demo" / "escrito-demo.pdf", base / "escrito.pdf")
    return {"long": status["examen_largo"]["id"], "mixed": status["examen_escrito"]["id"], "group": SCHOOL_GROUP}

def wait_server():
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/estado", timeout=1)
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit("El programa no encendió a tiempo.")


def capture(base, shots, ids):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("Falta Playwright: pip install playwright") from None
    shots.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{PORT}"

    def shoot(page, name):
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / f"{name}.png"))

    def top(page, selector, margin=70):
        page.evaluate("([s, m]) => window.scrollTo(0, document.querySelector(s).getBoundingClientRect().top + window.scrollY - m)", [selector, margin])

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge")
        except Exception:
            browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        page.goto(url + "/")
        page.wait_for_timeout(1200)
        page.evaluate("document.getElementById('tutorial') && (document.getElementById('tutorial').hidden = true)")
        shoot(page, "01-inicio")

        page.goto(url + "/grupos")
        page.wait_for_timeout(1000)
        shoot(page, "02-grupos")

        page.goto(url + "/examenes")
        page.wait_for_timeout(1200)
        group = ids["group"]
        page.click(f'#group-chips button[data-g="{group}"]')
        page.click('#materia-chips button[data-m="Lenguaje"]')
        page.wait_for_timeout(500)
        top(page, "#group-chips", 110)
        shoot(page, "03-pasos")

        page.locator("#slots .slot:not(.done):not([disabled])").first.click()
        page.click("#add-opc")
        card = page.locator("#series .serie").first
        for box in card.locator("[data-pick]:not([disabled])").all()[:5]:
            box.check()
        card.locator('[data-f="puntos"]').fill("10")
        page.wait_for_timeout(500)
        top(page, "#series", 60)
        shoot(page, "04-series")

        page.click("#preview-exam")
        page.wait_for_timeout(1800)
        shoot(page, "05-vista")
        page.keyboard.press("Escape")

        page.goto(url + "/calificar")
        page.wait_for_timeout(1200)
        page.select_option("#materia", "Matemática")
        page.wait_for_timeout(500)
        page.select_option("#examen", ids["long"])
        page.wait_for_timeout(500)
        page.evaluate("document.querySelector('main section details').open = true")
        top(page, "#drop", 150)
        shoot(page, "06-subir")

        page.set_input_files("#archivos", str(base / "entrega.pdf"))
        page.wait_for_selector(".tally", timeout=120000)
        page.wait_for_timeout(700)
        top(page, "#avance", 40)
        shoot(page, "07-resultado")

        page.select_option("#materia", "Lenguaje")
        page.wait_for_timeout(500)
        page.select_option("#examen", ids["mixed"])
        page.wait_for_timeout(500)
        page.set_input_files("#archivos", str(base / "escrito.pdf"))
        page.wait_for_selector("#revision:not([hidden])", timeout=120000)
        page.wait_for_timeout(1200)
        top(page, "#revision", 20)
        shoot(page, "08-revision")

        page.select_option("#materia", "Matemática")
        page.wait_for_timeout(500)
        page.select_option("#examen", ids["long"])
        page.wait_for_timeout(1500)
        page.evaluate("document.querySelector('#corregir').open = true")
        page.locator("#hojas button[data-sheet]").first.click()
        page.wait_for_selector("#fix-save")
        page.wait_for_timeout(800)
        page.wait_for_timeout(1200)
        top(page, "#corregir-box .review", 20)
        page.wait_for_timeout(600)
        shoot(page, "09-corregir")

        page.goto(url + "/notas")
        page.wait_for_timeout(1500)
        shoot(page, "10-notas")

        page.goto(url + "/boletin")
        page.wait_for_selector(".card-sheet")
        page.wait_for_timeout(800)
        page.evaluate("window.scrollTo(0, 380)")
        shoot(page, "11-boletin")

        page.goto(url + "/analisis")
        page.wait_for_timeout(1500)
        page.click('#modes [data-mode="materia"]')
        page.wait_for_timeout(1200)
        shoot(page, "12-analisis")
        page.locator("article.person").first.scroll_into_view_if_needed()
        top(page, "article.person", 30)
        shoot(page, "13-alumno")
        page.click('#modes [data-mode="general"]')
        page.wait_for_timeout(1200)
        page.evaluate("window.scrollTo(0, 0)")
        shoot(page, "14-general")
        browser.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    base = Path(sys.argv[1]).resolve()
    base.mkdir(parents=True, exist_ok=True)
    ids = seed(base)
    env = dict(os.environ)
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_server()
        capture(base, base / "capturas", ids)
    finally:
        server.terminate()
    print(f"Capturas en {base / 'capturas'}")


if __name__ == "__main__":
    main()
