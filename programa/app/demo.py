"""Genera un grupo, marca las hojas y las pasa por la misma cámara simulada."""

import random

from app.grade import mark_bubbles, pil_to_bgr, simulate_photo
from app.render import render_sheet
from app.service import class_report, create_diagnostic, grade_photo
from app.store import SHEETS, load, update

DEMO_NAMES = [
    "Ana",
    "Luis",
    "María",
    "Pedro",
    "Sofía",
    "Diego",
    "Lucía",
    "Jorge",
    "Valeria",
    "Hugo",
]


def choices_for(sheet, student_index):
    choices = []
    for question in sheet["questions"]:
        if question["skill"] == "area" and question.get("trap") is not None:
            if student_index < 7:
                choices.append(question["trap"])
            elif student_index < 9:
                choices.append(question["answer"])
            else:
                choices.append(2)
        elif student_index % 5 == 0 and question.get("trap") is not None:
            choices.append(question["trap"])
        else:
            choices.append(question["answer"])
    return choices


SCHOOL_GROUP = "Demo Sexto A"
SCHOOL_STUDENTS = ["Ana López", "Beto Pérez", "Carla Ruiz", "Daniel Soto", "Elena Cruz", "Fernando Gómez", "Gabriela Díaz", "Hugo Morales"]
SCHOOL_ABILITY = [0.95, 0.85, 0.8, 0.7, 0.62, 0.5, 0.4, 0.3]
HANDWRITING = ["Un nino busca a su perro y lo", "encuentra en la casa de su abuela.", "Lo importante es que nunca se rinde", "y pide ayuda a sus amigos."]
DEMO_DIR = SHEETS / "demo"


def _school_questions():
    """Preguntas de la demostración: se guardan aparte del banco para no gastar el límite de 40."""
    from app.service import _new_id, _now

    sums_math = [(3, 4), (5, 6), (7, 8), (9, 4), (6, 6), (8, 7), (12, 3), (11, 5), (4, 9), (7, 7), (6, 9), (8, 8), (9, 9), (5, 5)]
    sums_lang = [(2, 3), (4, 5), (6, 7), (8, 9), (3, 9), (5, 7), (4, 8), (2, 9)]
    rows = []
    for materia, sums in (("Matemática", sums_math), ("Lenguaje", sums_lang)):
        for a, b in sums:
            rows.append({"prompt": f"{materia}: ¿cuánto es {a} × {b}?", "answer": str(a * b), "criterion": "", "skill": "general", "materia": materia, "kind": "cerrada"})
    for materia, subjects in (("Matemática", ["cómo resolviste un problema", "para qué sirve multiplicar"]), ("Lenguaje", ["de qué trata el cuento", "cuál es la idea principal"])):
        for text in subjects:
            rows.append({"prompt": f"{materia}: explica con tus palabras {text}.", "answer": "", "criterion": "Cuenta la idea principal con sus palabras.", "skill": "general", "materia": materia, "kind": "abierta"})

    def mutate(db):
        from app.materias import ensure_materias

        db.setdefault("authored", [])
        ensure_materias(db)
        ids = {}
        used = {row["id"] for row in db["authored"]}
        for row in rows:
            if row["materia"] not in db["materias"]:
                db["materias"].append(row["materia"])
            new_id = _new_id(used)
            used.add(new_id)
            db["authored"].append({"id": new_id, **row, "created": _now()})
            ids.setdefault((row["materia"], row["kind"]), []).append(new_id)
        db["demo"] = {"group": SCHOOL_GROUP, "questions": [item for group in ids.values() for item in group]}
        return ids

    return update(mutate)


def _grade_school_exam(form_id, rng):
    from app.service import grade_photo, save_interpretation
    from app.series import bubble_slots

    db = load()
    for name, ability in zip(SCHOOL_STUDENTS, SCHOOL_ABILITY):
        pages = sorted(
            (sheet for sheet in db["sheets"].values() if sheet["form_id"] == form_id and sheet["student_name"] == name),
            key=lambda sheet: sheet.get("pagina") or 1,
        )
        for sheet in pages:
            rows = [q for q in sheet["questions"] if q.get("format") != "abierta"]
            picks = [q["answer"] if rng.random() < ability else rng.choice([i for i in range(4) if i != q["answer"]]) for q in rows]
            photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(sheet)), picks, bubble_slots(sheet)), seed=rng.randrange(10000))
            result = grade_photo(photo, form_id)
            if result.get("needs_review"):
                marks = rng.choices(["logrado", "parcial", "aun_no"], weights=[ability, 0.3, 1.05 - ability], k=len(result["items"]))
                save_interpretation(sheet["id"], marks)


def _write_pdf(path, pages):
    import cv2
    from PIL import Image

    images = [Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB)) for page in pages]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=150)


def simulate_school(seed=11):
    """Una escuela de ejemplo completa: grupo, exámenes calificados con notas y análisis, y dos PDF
    «escaneados» para probar la subida de hojas (con una hoja que falta y un alumno sin entregar)."""
    import cv2
    import numpy as np

    from app.series import bubble_slots
    from app.service import create_series_exam, save_group

    remove_school()
    rng = random.Random(seed)
    ids = _school_questions()
    math, math_open = ids[("Matemática", "cerrada")], ids[("Matemática", "abierta")]
    lang, lang_open = ids[("Lenguaje", "cerrada")], ids[("Lenguaje", "abierta")]

    def serie(tipo, picked, points):
        return {"tipo": tipo, "question_ids": picked, "puntos": points}

    def meta(bimestre, tipo, numero=1, total=20):
        return {"bimestre": bimestre, "tipo": tipo, "numero": numero, "nota_total": total}

    save_group(SCHOOL_GROUP, SCHOOL_STUDENTS)
    forms = []
    plan = [
        ([serie("opciones", math[:6], 10), serie("escrita", math_open, 10)], "Matemática", meta(1, "parcial")),
        ([serie("opciones", math[:7], 10), serie("opciones", math[7:], 10)], "Matemática", meta(1, "final")),
        ([serie("opciones", lang, 12), serie("escrita", lang_open, 8)], "Lenguaje", meta(1, "parcial")),
    ]
    for series, materia, info in plan:
        made = create_series_exam(SCHOOL_GROUP, [], rng, series, materias=[materia], meta=info)
        forms.append(made["form_id"])
        _grade_school_exam(made["form_id"], rng)
    long_exam = create_series_exam(SCHOOL_GROUP, [], rng, [serie("opciones", math[:7], 10), serie("opciones", math[7:], 10)], materias=["Matemática"], meta=meta(2, "parcial"))
    mixed_exam = create_series_exam(SCHOOL_GROUP, [], rng, [serie("opciones", lang[:4], 10), serie("escrita", lang_open, 10)], materias=["Lenguaje"], meta=meta(2, "final", 1, 30))
    forms += [long_exam["form_id"], mixed_exam["form_id"]]
    db = load()

    def sheets_of(exam):
        by = {}
        for info in exam["sheets"]:
            sheet = db["sheets"][info["id"]]
            by.setdefault(sheet["student_name"], []).append(sheet)
        for pages in by.values():
            pages.sort(key=lambda sheet: sheet["pagina"])
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

    long_by = sheets_of(long_exam)
    stack = []
    for name in SCHOOL_STUDENTS:
        if name == "Daniel Soto":
            continue  # no entregó
        for page in long_by[name]:
            if name == "Beto Pérez" and page["pagina"] == 2:
                continue  # le falta una hoja
            stack.append(scan(page, rng.uniform(-0.6, 0.6)))
    stack.insert(3, np.full((1754, 1240, 3), 255, np.uint8))
    rng.shuffle(stack)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    _write_pdf(DEMO_DIR / "entrega-demo.pdf", stack)
    mixed_by = sheets_of(mixed_exam)
    _write_pdf(DEMO_DIR / "escrito-demo.pdf", [scan(mixed_by[name][0], 0.3, ink=True) for name in ("Ana López", "Hugo Morales")])

    def remember(db):
        db["demo"]["forms"] = forms
        db["demo"]["largo"] = long_exam["form_id"]
        db["demo"]["escrito"] = mixed_exam["form_id"]

    update(remember)
    return school_status()


def school_status():
    from app.notas import form_meta

    db = load()
    info = db.get("demo")
    if not info or not info.get("forms"):
        return {"existe": False}
    titles = {}
    for key in ("largo", "escrito"):
        form = db["forms"].get(info.get(key) or "")
        titles[key] = form_meta(form)["titulo_completo"] if form else ""
    return {
        "existe": True,
        "grupo": info["group"],
        "examen_largo": {"id": info.get("largo"), "titulo": titles["largo"], "materia": "Matemática", "pdf": "/archivos/demo/entrega-demo.pdf"},
        "examen_escrito": {"id": info.get("escrito"), "titulo": titles["escrito"], "materia": "Lenguaje", "pdf": "/archivos/demo/escrito-demo.pdf"},
    }


def remove_school():
    """Borra la demostración completa: grupo, exámenes, notas, escaneos y sus preguntas."""
    import shutil

    from app.service import delete_group, purge_exam

    db = load()
    info = db.get("demo") or {}
    forms = set(info.get("forms") or [])
    forms |= {form_id for form_id, form in db["forms"].items() if (form.get("group") or "").strip().lower() == SCHOOL_GROUP.lower()}
    for form_id in forms:
        try:
            purge_exam(form_id)
        except ValueError:
            pass
    try:
        delete_group(SCHOOL_GROUP)
    except (ValueError, KeyError):
        pass

    def clean(db):
        wanted = set((db.get("demo") or {}).get("questions") or [])
        db["authored"] = [row for row in db.get("authored") or [] if row["id"] not in wanted]
        db.pop("demo", None)

    update(clean)
    shutil.rmtree(DEMO_DIR, ignore_errors=True)
    return {"ok": True}


def simulate_class(group="6A", seed=21):
    created = create_diagnostic(
        group,
        DEMO_NAMES,
        random.Random(seed),
        source="bank",
        meta={"tipo": "diagnostico", "nombre": "Clase de ejemplo", "nota_total": 100},
    )
    db = load()
    graded = []
    for index, info in enumerate(created["sheets"]):
        sheet = db["sheets"][info["id"]]
        page = mark_bubbles(pil_to_bgr(render_sheet(sheet)), choices_for(sheet, index))
        photo = simulate_photo(page, seed=100 + index)
        graded.append(grade_photo(photo))
    report = class_report(group, created["form_id"])
    return {"sheets": created["sheets"], "graded": graded, "patterns": report["patterns"]}
