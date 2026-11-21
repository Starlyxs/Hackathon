"""Toma las capturas del tutorial con datos de ejemplo (nunca toca tus datos reales).

Uso:
    pip install playwright                      (solo para esta herramienta)
    python herramientas/capturar_tutorial.py CARPETA_DE_SALIDA
    python herramientas/crear_tutorial.py CARPETA_DE_SALIDA/capturas

Prepara un grupo de ejemplo con exámenes calificados, enciende el programa en el puerto 8765 con
esa base temporal, sube un PDF escaneado de ejemplo y fotografía cada pantalla (1280x720).
Necesita Microsoft Edge o Google Chrome instalado.
"""

import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PORT = 8765
STUDENTS = ["Ana López", "Beto Pérez", "Carla Ruiz", "Daniel Soto", "Elena Cruz", "Fernando Gómez", "Gabriela Díaz", "Hugo Morales"]
ABILITY = [0.95, 0.85, 0.8, 0.7, 0.62, 0.5, 0.4, 0.3]
HANDWRITING = ["Un nino busca a su perro y lo", "encuentra en la casa de su abuela.", "Lo importante es que nunca se rinde", "y pide ayuda a sus amigos."]


def seed(base):
    """Crea la base de ejemplo. Debe correr antes de importar la app."""
    data = base / "datos"
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    os.environ["EDU_STORE"] = str(data / "store.json")
    os.environ["EDU_SHEETS"] = str(data / "sheets")

    import cv2
    import numpy as np
    from PIL import Image

    from app.grade import mark_bubbles, pil_to_bgr, simulate_photo
    from app.render import render_sheet
    from app.series import bubble_slots
    from app.service import add_question, create_series_exam, grade_photo, save_group, save_interpretation
    from app.store import load

    rng = random.Random(11)

    def closed(materia, sums):
        return [add_question(f"{materia}: ¿cuánto es {a} × {b}?", str(a * b), "general", materia)["id"] for a, b in sums]

    def opened(materia, subjects):
        return [
            add_question(f"{materia}: explica con tus palabras {text}.", materia=materia, kind="abierta", criterion="Cuenta la idea principal con sus palabras.")["id"]
            for text in subjects
        ]

    math = closed("Matemática", [(3, 4), (5, 6), (7, 8), (9, 4), (6, 6), (8, 7), (12, 3), (11, 5), (4, 9), (7, 7), (6, 9), (8, 8), (9, 9), (5, 5)])
    math_open = opened("Matemática", ["cómo resolviste un problema", "para qué sirve multiplicar"])
    lang = closed("Lenguaje", [(2, 3), (4, 5), (6, 7), (8, 9), (3, 9), (5, 7), (4, 8), (2, 9)])
    lang_open = opened("Lenguaje", ["de qué trata el cuento", "cuál es la idea principal"])

    def serie(tipo, ids, puntos):
        return {"tipo": tipo, "question_ids": ids, "puntos": puntos}

    def meta(bimestre, tipo, numero=1, total=20):
        return {"bimestre": bimestre, "tipo": tipo, "numero": numero, "nota_total": total}

    save_group("Sexto A", STUDENTS)
    abilities = dict(zip(STUDENTS, ABILITY))

    def grade_all(form_id):
        db = load()
        for name, ability in abilities.items():
            pages = sorted((s for s in db["sheets"].values() if s["form_id"] == form_id and s["student_name"] == name), key=lambda s: s.get("pagina") or 1)
            for sheet in pages:
                rows = [q for q in sheet["questions"] if q.get("format") != "abierta"]
                picks = [q["answer"] if rng.random() < ability else rng.choice([i for i in range(4) if i != q["answer"]]) for q in rows]
                photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(sheet)), picks, bubble_slots(sheet)), seed=rng.randrange(10000))
                result = grade_photo(photo, form_id)
                if result.get("needs_review"):
                    marks = rng.choices(["logrado", "parcial", "aun_no"], weights=[ability, 0.3, 1.05 - ability], k=len(result["items"]))
                    save_interpretation(sheet["id"], marks)

    made = {}
    plan = [
        ("mate1", [serie("opciones", math[:6], 10), serie("escrita", math_open, 10)], "Matemática", meta(1, "parcial")),
        ("mate2", [serie("opciones", math[:7], 10), serie("opciones", math[7:], 10)], "Matemática", meta(1, "final")),
        ("leng1", [serie("opciones", lang, 12), serie("escrita", lang_open, 8)], "Lenguaje", meta(1, "parcial")),
    ]
    for key, series, materia, info in plan:
        made[key] = create_series_exam("Sexto A", [], rng, series, materias=[materia], meta=info)
        grade_all(made[key]["form_id"])

    # Dos exámenes que se quedan sin calificar: se suben como PDF escaneado.
    long_exam = create_series_exam("Sexto A", [], rng, [serie("opciones", math[:7], 10), serie("opciones", math[7:], 10)], materias=["Matemática"], meta=meta(2, "parcial"))
    mixed_exam = create_series_exam("Sexto A", [], rng, [serie("opciones", lang[:4], 10), serie("escrita", lang_open, 10)], materias=["Lenguaje"], meta=meta(2, "final", 1, 30))
    db = load()

    def sheets_of(exam):
        by = {}
        for info in exam["sheets"]:
            sheet = db["sheets"][info["id"]]
            by.setdefault(sheet["student_name"], []).append(sheet)
        for pages in by.values():
            pages.sort(key=lambda s: s["pagina"])
        return by

    def scan(sheet, angle, ink=False):
        rows = [q["answer"] if rng.random() < 0.85 else rng.choice([i for i in range(4) if i != q["answer"]]) for q in sheet["questions"] if q.get("format") != "abierta"]
        bgr = mark_bubbles(pil_to_bgr(render_sheet(sheet)), rows, bubble_slots(sheet))
        if ink:
            boxes = [item["caja"] for item in sheet.get("layout") or [] if item.get("t") == "q_open"]
            for box, offset in zip(boxes, (0, 2)):
                for line, text in enumerate(HANDWRITING[offset : offset + 2]):
                    cv2.putText(bgr, text, (box[0] + 22, box[1] + 30 + line * 36), cv2.FONT_HERSHEY_SCRIPT_COMPLEX, 0.9, (150, 70, 25), 2, cv2.LINE_AA)
        height, width = bgr.shape[:2]
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        return cv2.warpAffine(bgr, matrix, (width, height), borderValue=(255, 255, 255))

    def pdf(path, pages):
        images = [Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB)) for page in pages]
        images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=150)

    long_by = sheets_of(long_exam)
    if any(len(pages) != 2 for pages in long_by.values()):
        raise SystemExit("El examen largo de ejemplo debía tener dos hojas por alumno.")
    stack = []
    for name in STUDENTS:
        if name == "Daniel Soto":
            continue  # no entregó
        for page in long_by[name]:
            if name == "Beto Pérez" and page["pagina"] == 2:
                continue  # le falta una hoja
            stack.append(scan(page, rng.uniform(-0.6, 0.6)))
    stack.insert(3, np.full((1754, 1240, 3), 255, np.uint8))
    rng.shuffle(stack)
    pdf(base / "entrega.pdf", stack)

    mixed_by = sheets_of(mixed_exam)
    pdf(base / "escrito.pdf", [scan(mixed_by[name][0], 0.3, ink=True) for name in ("Ana López", "Hugo Morales")])
    return {"long": long_exam["form_id"], "mixed": mixed_exam["form_id"]}


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
        page.click('#group-chips button[data-g="Sexto A"]')
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

        page.goto(url + "/notas")
        page.wait_for_timeout(1500)
        shoot(page, "09-notas")

        page.goto(url + "/analisis")
        page.wait_for_timeout(1500)
        page.click('#modes [data-mode="materia"]')
        page.wait_for_timeout(1200)
        shoot(page, "10-analisis")
        page.locator("article.person").first.scroll_into_view_if_needed()
        top(page, "article.person", 30)
        shoot(page, "11-alumno")
        page.click('#modes [data-mode="general"]')
        page.wait_for_timeout(1200)
        page.evaluate("window.scrollTo(0, 0)")
        shoot(page, "12-general")
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
