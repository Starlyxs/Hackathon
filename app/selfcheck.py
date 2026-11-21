"""Comprueba generación, lectura de burbujas y el patrón del grupo.

Usa una base aparte para no borrar las hojas reales del maestro.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["EDU_STORE"] = str(ROOT / "data" / "selfcheck.json")
os.environ["EDU_SHEETS"] = str(ROOT / "data" / "selfcheck-sheets")

from app.demo import simulate_class
from app.grade import GradeError, mark_bubbles, pil_to_bgr, simulate_photo
from app.render import render_sheet
from app.service import grade_photo
from app.store import ensure_dirs, load


def check_perfect_sheet():
    import random

    from app.service import create_diagnostic

    created = create_diagnostic("selfcheck", ["Camila"], random.Random(3), source="bank")
    sheet = load()["sheets"][created["sheets"][0]["id"]]
    choices = [question["answer"] for question in sheet["questions"]]
    photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(sheet)), choices), seed=7)
    result = grade_photo(photo)
    if result["student_name"] != "Camila":
        raise SystemExit(f"El QR no identificó al alumno: {result['student_name']}")
    if result["score"] != result["total"]:
        missed = [item for item in result["items"] if not item["correct"]]
        raise SystemExit(f"Una hoja bien contestada salió {result['score']}/{result['total']}: {missed}")
    print(f"Hoja limpia: {result['student_name']} {result['score']}/{result['total']}")


def check_class_pattern():
    report = simulate_class("6A-demo")
    messages = [item["message"] for item in report["patterns"]]
    print("Patrones:")
    for message in messages:
        print(f"  - {message}")
    expected = "confunde el área con el perímetro"
    if not any(expected in message and "70%" in message for message in messages):
        raise SystemExit("No apareció el patrón de área contra perímetro.")
    scores = [item["score"] for item in report["graded"]]
    if any(score != item["total"] and item["student_name"] in {"Pedro"} for item, score in zip(report["graded"], scores)):
        pass
    print(f"Grupo simulado: {len(report['graded'])} hojas calificadas.")


def check_authored_variants():
    import random
    import re

    from app.service import add_question, create_diagnostic, delete_question, list_questions
    from app.variants import preview_variants

    for row in list_questions()["questions"]:
        delete_question(row["id"])
    add_question("Un rectángulo mide 5 cm por 3 cm. ¿Cuál es su área?", "15", "area")
    add_question("¿Cuánto es 1/2 + 1/4?", "3/4", "fracciones")
    add_question("Lee: «El gato duerme en la silla.» ¿Quién duerme?", "el gato", "comprension")
    created = create_diagnostic("variantes", ["Ana", "Luis", "María"], random.Random(5), source="authored")
    sheets = [load()["sheets"][info["id"]] for info in created["sheets"]]
    areas = [sheet["questions"][0]["prompt"] for sheet in sheets]
    if len(set(areas)) < 3:
        raise SystemExit(f"Las variantes de área salieron iguales: {areas}")
    for sheet in sheets:
        area = sheet["questions"][0]
        nums = [int(n) for n in re.findall(r"\d+", area["prompt"])]
        correct = area["options"][area["answer"]]
        if str(nums[0] * nums[1]) not in correct:
            raise SystemExit(f"Clave mal calculada: {area}")
        if area.get("trap") is None:
            raise SystemExit(f"Faltó la trampa de perímetro: {area}")
    if len({sheet["questions"][1]["prompt"] for sheet in sheets}) < 2:
        raise SystemExit("Las fracciones no variaron.")
    answers = {sheet["questions"][2]["options"][sheet["questions"][2]["answer"]] for sheet in sheets}
    if answers != {"el gato"}:
        raise SystemExit(f"La respuesta de lectura cambió: {answers}")
    sheet = sheets[0]
    choices = [question["answer"] for question in sheet["questions"]]
    photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(sheet)), choices), seed=11)
    result = grade_photo(photo)
    if result["score"] != result["total"]:
        raise SystemExit(f"Variante bien contestada salió {result['score']}/{result['total']}")
    preview = preview_variants("Luis tenía 15 pesos y gastó 7. ¿Cuánto le queda?", "8", "operaciones")
    if len({row["prompt"] for row in preview}) < 2:
        raise SystemExit(f"La vista previa no varió la resta: {preview}")
    print(f"Variantes por alumno: {areas[0]} | {areas[1]}")


def check_notas_y_bimestres():
    import random

    from app.notas import grid, yearly
    from app.service import create_diagnostic, delete_exam

    group = f"notas-{random.randrange(10**6)}"
    parcial = {"tipo": "parcial", "bimestre": 2, "numero": 1, "nota_total": 20}
    first = create_diagnostic(group, ["Camila", "Raúl"], random.Random(1), source="bank", meta=parcial)
    try:
        create_diagnostic(group, ["Camila"], random.Random(2), source="bank", meta=parcial)
    except ValueError as exc:
        if "Ya existe Parcial 1" not in str(exc):
            raise SystemExit(f"Mensaje de duplicado inesperado: {exc}") from exc
    else:
        raise SystemExit("Se pudo crear dos veces el Parcial 1 del bimestre 2.")
    create_diagnostic(group, ["Camila", "Raúl"], random.Random(3), source="bank", meta={**parcial, "numero": 2, "nota_total": 20})
    create_diagnostic(
        group,
        ["Camila", "Raúl"],
        random.Random(4),
        source="bank",
        meta={"tipo": "final", "bimestre": 2, "nota_total": 40},
    )
    db = load()
    for index, info in enumerate(first["sheets"]):
        sheet = db["sheets"][info["id"]]
        answers = [q["answer"] for q in sheet["questions"]]
        if index == 1:
            answers = [None] * len(answers)
            answers[0] = sheet["questions"][0]["answer"]
        photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(sheet)), answers), seed=40 + index)
        result = grade_photo(photo)
        if index == 0 and result["score"] != result["total"]:
            raise SystemExit("La hoja perfecta del parcial no sacó todo.")
    data = grid(load(), group, 2)
    camila = next(row for row in data["students"] if row["student_name"] == "Camila")
    raul = next(row for row in data["students"] if row["student_name"] == "Raúl")
    parcial_id = first["form_id"]
    if camila["cells"][parcial_id]["nota_real"] != 20:
        raise SystemExit(f"Nota real esperada 20, salió {camila['cells'][parcial_id]['nota_real']}")
    expected = round(20 / 8, 1)
    if raul["cells"][parcial_id]["nota_real"] != expected:
        raise SystemExit(f"Nota real esperada {expected}, salió {raul['cells'][parcial_id]['nota_real']}")
    if raul["cells"][parcial_id]["nota_relativa"] != round(20 * expected / 20, 1):
        raise SystemExit("La nota relativa no escaló contra el mejor.")
    if camila["total_real"] != 20:
        raise SystemExit("El total del bimestre sumó mal.")
    year = yearly(load(), group)
    block = year["bimestres"][1]
    if block["max_zona"] != 40 or block["max_final"] != 40 or block["max_total"] != 80:
        raise SystemExit(f"Los máximos del bimestre salieron mal: {block}")
    if year["bimestres"][0]["max_total"] is not None:
        raise SystemExit("El bimestre 1 no tiene exámenes y debía quedar vacío.")
    delete_exam(parcial_id)
    create_diagnostic(group, ["Camila"], random.Random(5), source="bank", meta=parcial)
    print("Notas: nota total, relativa, duplicados bloqueados y resumen por bimestre.")


def check_grupos_apagar_papelera():
    import random

    from app.grade import quick_sheet_id
    from app.service import (
        create_diagnostic,
        delete_group,
        list_my_groups,
        overview,
        restore_exam,
        save_group,
        set_exam_off,
        sheet_status,
        trash_exam,
    )

    group = f"grupo-{random.randrange(10**6)}"
    save_group(group, ["Ana", "Luis", "ana", "  María  "])
    mine = next(row for row in list_my_groups()["groups"] if row["name"] == group)
    if mine["students"] != ["Ana", "Luis", "María"]:
        raise SystemExit(f"La lista del grupo salió mal: {mine['students']}")
    save_group(group.upper(), ["Ana", "Luis", "María"])
    if sum(1 for row in list_my_groups()["groups"] if row["name"].lower() == group.lower()) != 1:
        raise SystemExit("Un grupo con otras mayúsculas se creó como grupo distinto.")

    bank = load()["authored"]
    closed = [row["id"] for row in bank if row.get("kind", "cerrada") != "abierta"][:2]
    if len(closed) < 2:
        raise SystemExit("El selfcheck necesita al menos dos preguntas cerradas.")
    meta = {"tipo": "parcial", "bimestre": 3, "numero": 1, "nota_total": 20}
    made = create_diagnostic(group.lower(), [], random.Random(8), meta=meta, question_ids=closed)
    db = load()
    sheets = [db["sheets"][info["id"]] for info in made["sheets"]]
    if len(sheets) != 3 or {sheet["group"] for sheet in sheets} != {group}:
        raise SystemExit("El examen no usó la lista del grupo o no unificó el nombre.")
    if any(len(sheet["questions"]) != 2 for sheet in sheets):
        raise SystemExit("El examen no respetó las preguntas elegidas.")
    if db["forms"][made["form_id"]]["question_ids"] != closed:
        raise SystemExit("El examen no guardó qué preguntas usó.")

    sheet = sheets[0]
    photo = simulate_photo(
        mark_bubbles(pil_to_bgr(render_sheet(sheet)), [q["answer"] for q in sheet["questions"]]), seed=77
    )
    if quick_sheet_id(photo) != sheet["id"]:
        raise SystemExit("La lectura rápida del QR no encontró la hoja.")
    other = grade_photo(photo, made["form_id"])
    if other["score"] != other["total"]:
        raise SystemExit("La hoja del examen elegido no se calificó.")
    try:
        grade_photo(photo, "no-es-este")
    except GradeError as exc:
        if "no del examen que estás calificando" not in str(exc):
            raise SystemExit(f"Mensaje de otro examen inesperado: {exc}") from exc
    else:
        raise SystemExit("Se calificó una hoja de otro examen.")

    set_exam_off(made["form_id"], True)
    if sheet_status(sheet["id"], made["form_id"])["ok"]:
        raise SystemExit("Un examen apagado sigue aceptando hojas.")
    try:
        grade_photo(photo, made["form_id"])
    except GradeError as exc:
        if "apagado" not in str(exc):
            raise SystemExit(f"Mensaje de examen apagado inesperado: {exc}") from exc
    else:
        raise SystemExit("Se calificó una hoja de un examen apagado.")
    set_exam_off(made["form_id"], False)
    if not sheet_status(sheet["id"], made["form_id"])["ok"]:
        raise SystemExit("Encender el examen no lo dejó listo.")

    trash_exam(made["form_id"])
    again = create_diagnostic(group, [], random.Random(9), meta=meta, question_ids=closed)
    trash_exam(again["form_id"])
    restore_exam(made["form_id"])
    if not overview()["siguiente"]["texto"]:
        raise SystemExit("El resumen de inicio salió vacío.")
    try:
        create_diagnostic(group, [], random.Random(10), meta=meta, question_ids=closed)
    except ValueError:
        pass
    else:
        raise SystemExit("Se creó dos veces el mismo examen.")
    first_materia = next(row["materia"] for row in bank if row["id"] == closed[0])
    from app.service import add_question

    stranger = add_question(
        "Explica con tus palabras por qué el agua es importante.",
        materia="Ciencias Sociales" if first_materia != "Ciencias Sociales" else "Matemática",
        kind="abierta",
        criterion="Dice que todos los seres vivos la necesitan.",
    )
    other_materia = [stranger["id"]]
    if other_materia:
        try:
            create_diagnostic(
                group,
                [],
                random.Random(11),
                materias=[first_materia],
                meta={**meta, "numero": 2},
                question_ids=other_materia,
            )
        except ValueError as exc:
            if "quita las preguntas de otra materia" not in str(exc):
                raise SystemExit(f"Mensaje de materia inesperado: {exc}") from exc
        else:
            raise SystemExit("Un examen de una materia aceptó preguntas de otra.")
    from app.notas import grid, yearly

    if len(grid(load(), group, None, first_materia)["exams"]) != 1:
        raise SystemExit("El cuadro de notas no mostró el examen de su materia.")
    if grid(load(), group, None, stranger["materia"])["exams"]:
        raise SystemExit("El cuadro de notas mezcló materias distintas.")
    if yearly(load(), group, stranger["materia"])["bimestres"][2]["examenes"]:
        raise SystemExit("Las notas del año mezclaron materias distintas.")
    result = delete_group(group)
    if result["examenes"] != 1:
        raise SystemExit("Eliminar el grupo no movió su examen a la papelera.")
    for _ in range(2):
        if any(row["name"].lower() == group.lower() for row in list_my_groups()["groups"]):
            raise SystemExit("El grupo eliminado volvió a aparecer.")
    restore_exam(made["form_id"])
    if not any(row["name"].lower() == group.lower() for row in list_my_groups()["groups"]):
        raise SystemExit("Restaurar el examen no devolvió su grupo.")
    print("Grupos, preguntas elegidas, examen apagado y papelera.")


def main():
    ensure_dirs()
    try:
        check_perfect_sheet()
        check_class_pattern()
        check_authored_variants()
        check_notas_y_bimestres()
        check_grupos_apagar_papelera()
    except GradeError as exc:
        print(f"Falló la visión: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Listo: la cámara simulada lee el QR, las burbujas y el patrón del grupo.")


if __name__ == "__main__":
    main()
