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


def check_series_exam():
    import io
    import random

    from PIL import Image

    from app.service import add_question, create_series_exam, preview_series_exam, save_group, save_interpretation
    from app.series import bubble_slots, save_image
    from app.notas import grid

    group = f"series-{random.randrange(10**6)}"
    save_group(group, ["Ana", "Luis"])
    closed = [
        add_question(f"Serie de prueba: ¿cuánto es {a} + {b}?", str(a + b), "general", "Matemática")["id"]
        for a, b in ((3, 4), (5, 6), (7, 8))
    ]
    opened = [
        add_question(f"Serie de prueba {n}: explica con tus palabras qué viste.", materia="Matemática", kind="abierta", criterion="Describe lo principal.")["id"]
        for n in (1, 2)
    ]
    buffer = io.BytesIO()
    Image.new("RGB", (400, 120), (180, 210, 190)).save(buffer, "PNG")
    picture = save_image(buffer.getvalue())

    def serie(tipo, ids, puntos, **more):
        return {"tipo": tipo, "question_ids": ids, "puntos": puntos, **more}

    meta = {"tipo": "parcial", "bimestre": 4, "numero": 1, "nota_total": 20}
    for bad, text in (
        ([serie("opciones", closed, 15), serie("escrita", opened, 8)], "suman 23"),
        ([serie("opciones", closed, 0)], "cuántos puntos"),
        ([serie("opciones", opened, 5)], "quita las preguntas del otro tipo"),
        ([serie("opciones", closed, 5), serie("escrita", closed[:1], 5)], "dos series"),
        ([serie("opciones", [], 5)], "no tiene preguntas"),
        ([serie("opciones", closed, 5, imagen="0123456789")], "imagen"),
    ):
        try:
            create_series_exam(group, [], random.Random(1), bad, materias=["Matemática"], meta=meta)
        except ValueError as exc:
            if text not in str(exc):
                raise SystemExit(f"Mensaje de series inesperado ({text}): {exc}") from exc
        else:
            raise SystemExit(f"Se aceptó una serie inválida ({text}).")

    good = [serie("opciones", closed, 12, instruccion="Marca la respuesta.", imagen=picture["id"]), serie("escrita", opened, 8)]
    preview = preview_series_exam(group, [], random.Random(2), good, materias=["Matemática"], meta=meta)
    if len(preview["pngs"]) != 1:
        raise SystemExit("Una serie corta debía caber en una sola hoja.")
    made = create_series_exam(group, [], random.Random(3), good, materias=["Matemática"], meta=meta)
    if len(made["sheets"]) != 2 or made["paginas"] != 1:
        raise SystemExit("El examen por series dejó hojas de más o de menos.")
    db = load()
    sheet = db["sheets"][made["sheets"][0]["id"]]
    if [q["puntos"] for q in sheet["questions"]] != [4, 4, 4, 4, 4]:
        raise SystemExit("No repartió los puntos de la serie entre sus preguntas.")
    answers = [q["answer"] for q in sheet["questions"] if q.get("format") != "abierta"]
    photo = simulate_photo(
        mark_bubbles(pil_to_bgr(render_sheet(sheet)), answers, bubble_slots(sheet)), seed=91
    )
    pending = grade_photo(photo, made["form_id"])
    if not pending.get("needs_review") or pending["opciones"]["bien"] != 3 or len(pending["items"]) != 2:
        raise SystemExit(f"La hoja mezclada no pidió revisar lo escrito: {pending}")
    saved = save_interpretation(sheet["id"], ["logrado", "parcial"])
    if saved["score"] != 18 or saved["total"] != 20:
        raise SystemExit(f"La nota de la hoja mezclada salió mal: {saved['score']}/{saved['total']}")
    # Luis responde 1 de 3 de opciones y deja lo escrito en cero.
    other = db["sheets"][made["sheets"][1]["id"]]
    mine = [q["answer"] for q in other["questions"] if q.get("format") != "abierta"]
    mine = [mine[0], None, None]
    photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(other)), mine, bubble_slots(other)), seed=92)
    grade_photo(photo, made["form_id"])
    saved = save_interpretation(other["id"], ["aun_no", "aun_no"])
    if saved["score"] != 4:
        raise SystemExit(f"Una sola acertada debía valer 4 puntos, salió {saved['score']}")
    data = grid(load(), group, 4)
    notas = {row["student_name"]: row["cells"][made["form_id"]]["nota_real"] for row in data["students"]}
    if notas != {"Ana" if sheet["student_name"] == "Ana" else "Luis": 18, ("Luis" if sheet["student_name"] == "Ana" else "Ana"): 4}:
        raise SystemExit(f"Las notas del examen por series salieron mal: {notas}")

    from app.service import class_analysis

    report = class_analysis(group, made["form_id"])
    people = {row["nombre"]: row for row in report["alumnos"]}
    low = people["Luis" if sheet["student_name"] == "Ana" else "Ana"]
    high = people[sheet["student_name"]]
    if not report["hay_datos"] or report["resumen"]["calificados"] != 2 or report["resumen"]["aprueban"] != 1:
        raise SystemExit(f"El resumen del análisis salió mal: {report['resumen']}")
    if low["nivel"] != "urgente" or not low["refuerzo"] or "en blanco" not in low["texto"]:
        raise SystemExit(f"El texto del alumno flojo salió mal: {low['texto']}")
    if high["nivel"] not in ("excelente", "bien") or low["nombre"] not in low["texto"]:
        raise SystemExit(f"El texto del alumno fuerte salió mal: {high['texto']}")
    if [row["nombre"] for row in report["series"]] != ["Serie I", "Serie II"] or sum(b["alumnos"] for b in report["distribucion"]) != 2:
        raise SystemExit("El análisis por serie o la distribución salieron mal.")
    for modo, extra in (("materia", {"materia": "Matemática"}), ("general", {})):
        wide = class_analysis(group, modo=modo, **extra)
        names = {row["nombre"]: row for row in wide["alumnos"]}
        if not wide["hay_datos"] or wide["resumen"]["calificados"] != 2 or wide["resumen"]["promedio_pct"] != 55:
            raise SystemExit(f"El análisis {modo} salió mal: {wide.get('resumen')}")
        if names[low["nombre"]]["pct"] != 20 or "lleva 20%" not in names[low["nombre"]]["texto"]:
            raise SystemExit(f"El texto del análisis {modo} salió mal: {names[low['nombre']]['texto']}")
        if modo == "general" and [row["nombre"] for row in wide["materias"]] != ["Matemática"]:
            raise SystemExit("El análisis general no separó por materia.")
        if [row["bimestre"] for row in wide["bimestres"]] != [4]:
            raise SystemExit("El análisis no separó por bimestre.")
    if class_analysis(group, modo="general", bimestre=2)["hay_datos"]:
        raise SystemExit("Un bimestre sin exámenes no debía tener análisis.")
    if class_analysis("grupo-que-no-existe")["hay_datos"]:
        raise SystemExit("Un grupo sin exámenes no debía tener análisis.")

    # Un examen largo pasa a una segunda hoja sin dejar hojas vacías.
    long_ids = [
        add_question(f"Serie larga: ¿cuánto es {n} + {n}?", str(n + n), "general", "Matemática")["id"]
        for n in range(2, 14)
    ]
    long_group = f"larga-{random.randrange(10**6)}"
    save_group(long_group, ["Ana"])
    long = create_series_exam(
        long_group,
        [],
        random.Random(4),
        [serie("opciones", long_ids[:6], 10, imagen=picture["id"]), serie("opciones", long_ids[6:], 10)],
        materias=["Matemática"],
        meta=meta,
    )
    if len(long["sheets"]) != 2 or long["paginas"] != 2:
        raise SystemExit(f"Se esperaban 2 hojas, salieron {len(long['sheets'])}.")
    db = load()
    pages = [db["sheets"][info["id"]] for info in long["sheets"]]
    if any(len(page["questions"]) < 3 for page in pages):
        raise SystemExit("Quedó una hoja casi vacía.")
    for index, page in enumerate(pages):
        answers = [q["answer"] for q in page["questions"]]
        photo = simulate_photo(mark_bubbles(pil_to_bgr(render_sheet(page)), answers, bubble_slots(page)), seed=95 + index)
        result = grade_photo(photo, long["form_id"])
        if result["score"] != result["total"]:
            raise SystemExit("Una hoja perfecta de series no sacó todos sus puntos.")
    final = grid(load(), long_group, 4)["students"][0]["cells"][long["form_id"]]
    if final["nota_real"] != 20:
        raise SystemExit(f"Las dos hojas debían sumar 20, salió {final['nota_real']}")
    print("Series: puntos repartidos, imagen, hojas sin espacios vacíos y nota por hoja.")


def _scan_like(bgr, angle=0.0, bw=False, turn=None):
    """Una página como la deja un escáner de celular: casi derecha, fondo blanco, a veces en blanco y negro."""
    import cv2

    height, width = bgr.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    out = cv2.warpAffine(bgr, matrix, (width, height), borderValue=(255, 255, 255))
    if bw:
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        out = cv2.cvtColor(cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15), cv2.COLOR_GRAY2BGR)
    if turn is not None:
        out = cv2.rotate(out, turn)
    return out


def _pdf_of(pages):
    import io

    import cv2
    from PIL import Image

    images = [Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB)) for page in pages]
    buffer = io.BytesIO()
    images[0].save(buffer, "PDF", save_all=True, append_images=images[1:], resolution=150)
    return buffer.getvalue()


def _wait_job(job):
    import time

    from app import escaneo

    for _ in range(900):
        data = escaneo.progress(job)
        if data["estado"] != "corriendo":
            return data
        time.sleep(0.2)
    raise SystemExit("La lectura del PDF no terminó a tiempo.")


def check_scan_pdf():
    import random

    import cv2
    import numpy as np

    from app import escaneo
    from app.notas import grid
    from app.series import bubble_slots
    from app.service import add_question, create_series_exam, save_group, save_interpretation

    def serie(tipo, ids, puntos):
        return {"tipo": tipo, "question_ids": ids, "puntos": puntos}

    meta = {"tipo": "parcial", "bimestre": 3, "numero": 1, "nota_total": 20}
    ids = [add_question(f"Escaneo: ¿cuánto es {n} + {n + 1}?", str(n + n + 1), "general", "Matemática")["id"] for n in range(2, 14)]
    group = f"escaneo-{random.randrange(10**6)}"
    save_group(group, ["Ana", "Beto", "Carla", "Dani"])
    made = create_series_exam(group, [], random.Random(5), [serie("opciones", ids[:6], 10), serie("opciones", ids[6:], 10)], materias=["Matemática"], meta=meta)
    db = load()
    by_student = {}
    for info in made["sheets"]:
        sheet = db["sheets"][info["id"]]
        by_student.setdefault(sheet["student_name"], []).append(sheet)
    for pages in by_student.values():
        pages.sort(key=lambda item: item["pagina"])
    if len(by_student["Ana"]) != 2:
        raise SystemExit("El examen de prueba debía tener dos hojas por alumno.")

    def page_image(sheet, right=True, **kwargs):
        answers = [q["answer"] for q in sheet["questions"]] if right else [None] * len(sheet["questions"])
        return _scan_like(mark_bubbles(pil_to_bgr(render_sheet(sheet)), answers, bubble_slots(sheet)), **kwargs)

    blank = np.full((1754, 1240, 3), 255, np.uint8)
    ana, beto, carla = by_student["Ana"], by_student["Beto"], by_student["Carla"]
    stack = [
        page_image(carla[1], angle=-0.7, turn=cv2.ROTATE_180),  # llega al revés y fuera de orden
        page_image(ana[0], angle=0.6),
        blank,
        page_image(beto[0], angle=-0.5, bw=True),  # filtro blanco y negro; a Beto le falta la hoja 2
        page_image(ana[1]),
        page_image(carla[0], angle=0.4, bw=True),
        page_image(ana[0], angle=0.2),  # Ana repetida
    ]
    data = _wait_job(escaneo.start([("curso.pdf", _pdf_of(stack))], made["form_id"]))
    summary = data["resumen"]
    if data["estado"] != "listo" or summary != {"calificadas": 5, "revisar": 0, "repetidas": 1, "blancas": 1, "errores": 0}:
        raise SystemExit(f"El PDF escaneado se leyó mal: {data['estado']} {summary} {[p['mensaje'] for p in data['paginas'] if p['mensaje']]}")
    status = data["examenes"][0]
    if status["completos"] != 2 or status["sin_entregar"] != ["Dani"]:
        raise SystemExit(f"El resumen de hojas completas salió mal: {status}")
    if [(row["alumno"], row["faltan"]) for row in status["incompletos"]] != [("Beto", ["hoja 2 de 2"])]:
        raise SystemExit(f"No avisó la hoja que falta: {status['incompletos']}")
    notas = {row["student_name"]: row["cells"][made["form_id"]] for row in grid(load(), group, 3)["students"]}
    if notas["Ana"]["nota_real"] != 20 or notas["Carla"]["nota_real"] != 20 or notas["Beto"]["state"] != "parcial":
        raise SystemExit(f"Las notas del PDF salieron mal: {notas}")
    if not escaneo.scan_url(carla[1]["id"]):
        raise SystemExit("No guardó la imagen del escaneo.")
    # La hoja que faltaba llega en otro archivo, como foto suelta: se completa.
    ok, encoded = cv2.imencode(".jpg", page_image(beto[1], angle=0.3), [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    again = _wait_job(escaneo.start([("beto-2.jpg", encoded.tobytes())], made["form_id"]))
    if again["resumen"]["calificadas"] != 1 or again["examenes"][0]["completos"] != 3:
        raise SystemExit(f"La hoja que faltaba no completó a Beto: {again['resumen']} {again['examenes']}")
    other = _wait_job(escaneo.start([("curso.pdf", _pdf_of(stack[:2]))], "no-es-este"))
    if other["resumen"]["errores"] != 2:
        raise SystemExit(f"Una hoja de otro examen no debía calificarse: {other['resumen']}")
    for bad_name, raw in (("roto.pdf", b"%PDF-1.4 esto no es un pdf"), ("texto.jpg", b"hola")):
        bad = _wait_job(escaneo.start([(bad_name, raw)], made["form_id"]))
        if bad["resumen"]["errores"] != 1 or bad["resumen"]["calificadas"]:
            raise SystemExit(f"Un archivo dañado debía avisar el error: {bad}")

    # Una hoja con preguntas escritas queda pendiente de revisión, con su imagen.
    opened = [
        add_question(f"Escaneo escrito {n}: explica con tus palabras qué viste.", materia="Matemática", kind="abierta", criterion="Describe lo principal.")["id"]
        for n in (1, 2)
    ]
    mixed_group = f"mixto-{random.randrange(10**6)}"
    save_group(mixed_group, ["Eva"])
    mixed = create_series_exam(
        mixed_group, [], random.Random(6),
        [serie("opciones", ids[:3], 12), serie("escrita", opened, 8)],
        materias=["Matemática"], meta={**meta, "bimestre": 2},
    )
    sheet = load()["sheets"][mixed["sheets"][0]["id"]]
    right = [q["answer"] for q in sheet["questions"] if q.get("format") != "abierta"]
    photo = mark_bubbles(pil_to_bgr(render_sheet(sheet)), right, bubble_slots(sheet))
    review = _wait_job(escaneo.start([("eva.pdf", _pdf_of([_scan_like(photo, angle=0.5)]))], mixed["form_id"]))
    waiting = escaneo.pending_reviews(mixed["form_id"])
    if review["resumen"]["revisar"] != 1 or len(waiting) != 1 or not waiting[0]["imagen"] or review["examenes"][0]["por_revisar"][0]["alumno"] != "Eva":
        raise SystemExit(f"La hoja con preguntas escritas no quedó por revisar: {review['resumen']} {waiting}")
    saved = save_interpretation(sheet["id"], ["logrado", "logrado"])
    if saved["score"] != 20 or escaneo.pending_reviews(mixed["form_id"]) or escaneo.completeness(load(), mixed["form_id"])["completos"] != 1:
        raise SystemExit("Revisar lo escrito no completó la hoja escaneada.")
    print("PDF escaneado: QR por página, hojas faltantes, repetidas, en blanco, al revés y revisión de lo escrito.")

    # Corregir una burbuja mal leída recalcula la nota y conserva lo escrito.
    from app import correccion

    info = correccion.detail(sheet["id"])
    if len(info["preguntas"]) != 3 or len(info["escritas"]) != 2 or info["score"] != 20 or not info["imagen"]:
        raise SystemExit(f"El detalle de la hoja salió mal: {info}")
    fixed = [question["choice"] for question in info["preguntas"]]
    fixed[0] = None
    correccion.fix(sheet["id"], fixed)
    after = correccion.detail(sheet["id"])
    if after["score"] != 16 or after["preguntas"][0]["status"] != "corregida" or len(after["escritas"]) != 2:
        raise SystemExit(f"La corrección no recalculó la nota: {after}")
    listed = correccion.list_sheets(mixed["form_id"])
    if len(listed) != 1 or listed[0]["estado"] != "calificada":
        raise SystemExit(f"La lista de hojas salió mal: {listed}")
    for bad in ([0, 1], [0, 1, 7]):
        try:
            correccion.fix(sheet["id"], bad)
        except ValueError:
            continue
        raise SystemExit("Se aceptó una corrección inválida.")
    if escaneo.count_scans(mixed["form_id"]) != 1 or escaneo.delete_scans(mixed["form_id"])["borradas"] != 1 or escaneo.count_scans(mixed["form_id"]):
        raise SystemExit("No borró las imágenes escaneadas del examen.")
    print("Corrección: una burbuja cambiada recalcula la nota y la hoja conserva lo escrito.")


def check_demo_and_report_cards():
    from app import boletin
    from app.demo import SCHOOL_GROUP, remove_school, school_status, simulate_school
    from app.notas import grid
    from app.service import class_analysis

    status = simulate_school()
    if not status["existe"] or status["grupo"] != SCHOOL_GROUP or not (Path(os.environ["EDU_SHEETS"]) / "demo" / "entrega-demo.pdf").exists():
        raise SystemExit(f"La prueba simulada no quedó lista: {status}")
    data = grid(load(), SCHOOL_GROUP, 1)
    if len(data["students"]) != 8 or not all(row["calificado"] for row in data["students"]):
        raise SystemExit("La prueba simulada debía tener 8 alumnos calificados.")
    if not class_analysis(SCHOOL_GROUP, modo="general")["hay_datos"]:
        raise SystemExit("La prueba simulada no tiene análisis.")
    cards = boletin.build(SCHOOL_GROUP)["alumnos"]
    if len(cards) != 8 or {row["materia"] for row in cards[0]["materias"]} != {"Lenguaje", "Matemática"} or not cards[0]["texto"]:
        raise SystemExit(f"El boletín salió mal: {cards[0]}")
    if len(boletin.build(SCHOOL_GROUP, "ana lópez")["alumnos"]) != 1:
        raise SystemExit("El boletín de un solo alumno salió mal.")
    # La misma subida del PDF de ejemplo avisa lo que falta, como en la demostración.
    from app import escaneo

    raw = (Path(os.environ["EDU_SHEETS"]) / "demo" / "entrega-demo.pdf").read_bytes()
    result = _wait_job(escaneo.start([("entrega-demo.pdf", raw)], status["examen_largo"]["id"]))
    exam = result["examenes"][0]
    if exam["completos"] != 6 or exam["sin_entregar"] != ["Daniel Soto"] or exam["incompletos"][0]["alumno"] != "Beto Pérez":
        raise SystemExit(f"El PDF de ejemplo no mostró lo que debía: {exam}")
    before = len(load()["authored"])
    remove_school()
    db = load()
    if school_status()["existe"] or any(f.get("group") == SCHOOL_GROUP and not f.get("papelera") for f in db["forms"].values()) or len(db["authored"]) >= before:
        raise SystemExit("Borrar la demostración dejó datos.")
    if SCHOOL_GROUP in db["groups"] or (Path(os.environ["EDU_SHEETS"]) / "demo").exists():
        raise SystemExit("Borrar la demostración dejó el grupo o los PDF.")
    print("Demostración: escuela de ejemplo, boletines, PDF de ejemplo y borrado completo.")


def main():
    import shutil

    # Siempre se parte de una base vacía: es solo la de las pruebas, nunca la del maestro.
    Path(os.environ["EDU_STORE"]).unlink(missing_ok=True)
    shutil.rmtree(os.environ["EDU_SHEETS"], ignore_errors=True)
    ensure_dirs()
    try:
        check_perfect_sheet()
        check_class_pattern()
        check_authored_variants()
        check_notas_y_bimestres()
        check_grupos_apagar_papelera()
        check_series_exam()
        check_scan_pdf()
        check_demo_and_report_cards()
    except GradeError as exc:
        print(f"Falló la visión: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("Listo: la cámara y el PDF simulados leen el QR, las burbujas y el patrón del grupo.")


if __name__ == "__main__":
    main()
