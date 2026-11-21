"""Genera un grupo, marca las hojas y las pasa por la misma cámara simulada."""

import random

from app.grade import mark_bubbles, pil_to_bgr, simulate_photo
from app.render import render_sheet
from app.service import class_report, create_diagnostic, grade_photo
from app.store import load

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
