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


def main():
    ensure_dirs()
    try:
        check_perfect_sheet()
        check_class_pattern()
        check_authored_variants()
        check_notas_y_bimestres()
    except GradeError as exc:
        print(f"Falló la visión: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Listo: la cámara simulada lee el QR, las burbujas y el patrón del grupo.")


if __name__ == "__main__":
    main()
