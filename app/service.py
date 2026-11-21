"""Arma diagnósticos, califica una foto y prepara la hoja de refuerzo."""

import random
import secrets
from datetime import datetime, timezone

from app.bank import BANK, SKILLS, build_questions
from app.grade import GradeError, align_sheet, read_bubbles, read_sheet_id
from app.materias import ensure_materias
from app.render import render_sheet, save_pdf
from app.store import SHEETS, load, update
from app.variants import vary_question


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(existing):
    while True:
        value = secrets.token_hex(4)
        if value not in existing:
            return value


def create_diagnostic(group, names, rng, source="auto", materias=None):
    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        raise ValueError("Escribe al menos un nombre.")
    chosen = [item.strip() for item in (materias or []) if item and item.strip()]

    def mutate(db):
        db.setdefault("authored", [])
        ensure_materias(db)
        use_authored = source == "authored" or (source == "auto" and db["authored"])
        if source == "authored" and not db["authored"]:
            raise ValueError("Agrega al menos una pregunta.")
        warnings = []
        shared = None
        closed = []
        opened = []
        if use_authored:
            seeds = list(db["authored"])
            if chosen:
                seeds = [item for item in seeds if item.get("materia") in chosen]
            closed = [item for item in seeds if item.get("kind", "cerrada") != "abierta"]
            opened = [item for item in seeds if item.get("kind") == "abierta"]
            if len(closed) > 8:
                warnings.append("La hoja de burbujas tiene espacio para 8 preguntas.")
            if len(opened) > 4:
                warnings.append("La hoja de interpretación tiene espacio para 4 preguntas.")
            closed = closed[:8]
            opened = opened[:4]
            if not closed and not opened:
                raise ValueError("No hay preguntas en las materias elegidas.")
        else:
            shared = build_questions(rng)
        form_id = _new_id(db["forms"])
        db["forms"][form_id] = {
            "id": form_id,
            "group": group,
            "kind": "diagnostico",
            "created": _now(),
            "questions": [item["prompt"] for item in (shared or closed or opened)],
        }
        created = []
        used = {}
        for name in names:
            if shared is not None:
                sheet = _new_sheet(db, group, name, "diagnostico", shared, form_id)
                created.append(_publish(sheet))
                continue
            if closed:
                questions = _variants_for_student(closed, rng, used)
                sheet = _new_sheet(
                    db,
                    group,
                    name,
                    "diagnostico",
                    questions,
                    form_id,
                    materia_label=_join_materias(closed),
                    label=f"{name} · opciones",
                )
                created.append(_publish(sheet))
            if opened:
                questions = [_open_question(item) for item in opened]
                sheet = _new_sheet(
                    db,
                    group,
                    name,
                    "diagnostico",
                    questions,
                    form_id,
                    sheet_format="abierta",
                    materia_label=_join_materias(opened),
                    label=f"{name} · interpretación",
                )
                created.append(_publish(sheet))
        return {
            "form_id": form_id,
            "sheets": created,
            "source": "authored" if use_authored else "bank",
            "warning": " ".join(warnings) or None,
        }

    return update(mutate)


def list_questions():
    def read(db):
        db.setdefault("authored", [])
        ensure_materias(db)
        return {"questions": list(db["authored"]), "materias": list(db["materias"])}

    return update(read)


def add_materia(name):
    name = " ".join(name.split())
    if len(name) < 3 or len(name) > 48:
        raise ValueError("Escribe el nombre de la materia, por ejemplo K'iche'.")

    def mutate(db):
        ensure_materias(db)
        if name not in db["materias"]:
            db["materias"].append(name)
        return {"materias": list(db["materias"])}

    return update(mutate)


def add_question(prompt, answer="", skill="general", materia="Matemática", kind="cerrada", criterion=""):
    prompt = " ".join(prompt.split())
    answer = " ".join(answer.split())
    criterion = " ".join(criterion.split())
    materia = " ".join(materia.split())
    if skill not in SKILLS:
        raise ValueError("Elige un tema de la lista.")
    if kind not in ("cerrada", "abierta"):
        raise ValueError("El tipo de pregunta no es válido.")
    if kind == "cerrada" and not answer:
        raise ValueError("Escribe la respuesta correcta.")
    if kind == "abierta" and len(criterion) < 8:
        raise ValueError("Escribe qué idea debe lograr el alumno.")
    if len(materia) < 3:
        raise ValueError("Elige una materia.")

    def mutate(db):
        db.setdefault("authored", [])
        ensure_materias(db)
        if materia not in db["materias"]:
            db["materias"].append(materia)
        if len(db["authored"]) >= 40:
            raise ValueError("El banco acepta hasta 40 preguntas.")
        item = {
            "id": _new_id({row["id"] for row in db["authored"]}),
            "prompt": prompt,
            "answer": answer,
            "criterion": criterion,
            "skill": skill,
            "materia": materia,
            "kind": kind,
            "created": _now(),
        }
        db["authored"].append(item)
        return item

    return update(mutate)


def delete_question(question_id):
    def mutate(db):
        db.setdefault("authored", [])
        db["authored"] = [row for row in db["authored"] if row["id"] != question_id]
        return {"ok": True}

    return update(mutate)


def create_reinforcement(group, student_name):
    def mutate(db):
        latest = _latest_for_student(db, group, student_name)
        if latest is None:
            raise ValueError("Ese alumno todavía no tiene un diagnóstico calificado.")
        weak = []
        for item in latest["items"]:
            if not item["correct"] and item["skill"] not in weak:
                weak.append(item["skill"])
        if not weak:
            weak = list(SKILLS.keys())[:1]
        open_sheet = latest["items"] and all(item.get("format") == "abierta" for item in latest["items"])
        if open_sheet:
            missed = [item["prompt"] for item in latest["items"] if item.get("status") != "logrado"]
            pool = [
                row
                for row in db.get("authored") or []
                if row.get("kind") == "abierta" and (not missed or row["prompt"] in missed)
            ]
            questions = [_open_question(row) for row in pool[:4]]
            if not questions:
                raise ValueError("No hay preguntas abiertas para repetir.")
            sheet = _new_sheet(
                db,
                group,
                student_name,
                "refuerzo",
                questions,
                None,
                sheet_format="abierta",
                materia_label=_join_materias(pool),
                label=f"{student_name} · interpretación",
            )
            return _publish(sheet)
        authored = [row for row in (db.get("authored") or []) if row.get("kind", "cerrada") != "abierta"]
        if authored:
            pool = [row for row in authored if row["skill"] in weak] or authored
            questions = _practice_variants(pool)
        else:
            used = {item["prompt"] for item in latest["items"]}
            questions = []
            for skill in weak:
                pool = [dict(q) for q in BANK if q["skill"] == skill and q["prompt"] not in used]
                questions.extend(pool[:2])
            if len(questions) < 4:
                for item in BANK:
                    if item["prompt"] not in used and all(q["prompt"] != item["prompt"] for q in questions):
                        questions.append(dict(item))
                    if len(questions) >= 6:
                        break
            questions = questions[:8]
        sheet = _new_sheet(db, group, student_name, "refuerzo", questions, None)
        return _publish(sheet)

    return update(mutate)


def grade_photo(image_bgr):
    aligned = align_sheet(image_bgr)
    sheet_id = read_sheet_id(aligned)
    preview = load().get("sheets", {}).get(sheet_id)
    if preview is None:
        raise GradeError("Ese QR no está en esta laptop. Genera la hoja desde aquí antes de calificarla.")
    if preview.get("format") == "abierta":
        return {
            "needs_review": True,
            "sheet_id": sheet_id,
            "student_name": preview["student_name"],
            "group": preview["group"],
            "items": [
                {
                    "prompt": question["prompt"],
                    "criterion": question.get("criterion") or "",
                    "materia": question.get("materia") or "",
                }
                for question in preview["questions"]
            ],
        }

    def mutate(db):
        sheet = db["sheets"].get(sheet_id)
        if sheet is None:
            raise GradeError("Ese QR no está en esta laptop. Genera la hoja desde aquí antes de calificarla.")
        choices, details = read_bubbles(aligned, len(sheet["questions"]))
        items = []
        score = 0
        for question, choice, detail in zip(sheet["questions"], choices, details):
            correct = choice is not None and choice == question["answer"]
            if correct:
                score += 1
            trap = (
                question.get("trap") is not None
                and choice is not None
                and choice == question["trap"]
                and not correct
            )
            items.append(
                {
                    "prompt": question["prompt"],
                    "skill": question["skill"],
                    "skill_name": SKILLS.get(question["skill"], question["skill"]),
                    "choice": choice,
                    "answer": question["answer"],
                    "correct": correct,
                    "status": detail["status"],
                    "format": "cerrada",
                    "trap": trap,
                    "trap_label": question.get("trap_label") if trap else None,
                }
            )
        result = {
            "sheet_id": sheet_id,
            "student_name": sheet["student_name"],
            "group": sheet["group"],
            "kind": sheet["kind"],
            "score": score,
            "total": len(items),
            "items": items,
            "created": _now(),
        }
        db["results"].append(result)
        return result

    return update(mutate)


def save_interpretation(sheet_id, marks):
    points = {"logrado": 1, "parcial": 0.5, "aun_no": 0}

    def mutate(db):
        sheet = db["sheets"].get(sheet_id)
        if sheet is None or sheet.get("format") != "abierta":
            raise ValueError("Esa hoja no es de interpretación.")
        if len(marks) != len(sheet["questions"]):
            raise ValueError("Falta calificar una respuesta.")
        items = []
        score = 0
        for question, mark in zip(sheet["questions"], marks):
            if mark not in points:
                raise ValueError("Marca cada respuesta como logrado, parcial o aún no.")
            score += points[mark]
            criterion = question.get("criterion") or "la idea"
            items.append(
                {
                    "prompt": question["prompt"],
                    "skill": question.get("skill") or "comprension",
                    "skill_name": question.get("materia") or "interpretación",
                    "choice": None,
                    "answer": None,
                    "correct": mark == "logrado",
                    "status": mark,
                    "format": "abierta",
                    "trap": mark == "aun_no",
                    "trap_label": f"no logra interpretar: {criterion[:90]}" if mark == "aun_no" else None,
                }
            )
        result = {
            "sheet_id": sheet_id,
            "student_name": sheet["student_name"],
            "group": sheet["group"],
            "kind": sheet["kind"],
            "score": score,
            "total": len(items),
            "items": items,
            "created": _now(),
        }
        db["results"].append(result)
        return result

    return update(mutate)


def class_report(group):
    def read(db):
        latest = {}
        for result in db["results"]:
            if result["group"] == group:
                latest[result["student_name"]] = result
        rows = list(latest.values())
        return {"students": len(rows), "results": rows, "patterns": patterns_from(rows)}

    return update(lambda db: read(db))


def patterns_from(results):
    if len(results) < 3:
        return []
    buckets = {}
    for result in results:
        seen_labels = set()
        for item in result["items"]:
            label = item.get("trap_label")
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            bucket = buckets.setdefault(label, {"students": 0, "skill_name": item["skill_name"]})
            bucket["students"] += 1
    messages = []
    total = len(results)
    for label, bucket in buckets.items():
        ratio = bucket["students"] / total
        if ratio < 0.5:
            continue
        percent = round(ratio * 100)
        messages.append(
            {
                "percent": percent,
                "skill_name": bucket["skill_name"],
                "message": f"El {percent}% de la clase {label}.",
            }
        )
    messages.sort(key=lambda item: item["percent"], reverse=True)
    return messages


def _join_materias(rows):
    names = []
    for row in rows:
        name = row.get("materia")
        if name and name not in names:
            names.append(name)
    return " · ".join(names)


def _open_question(seed):
    return {
        "prompt": seed["prompt"],
        "format": "abierta",
        "criterion": seed.get("criterion") or "",
        "skill": seed.get("skill") or "comprension",
        "materia": seed.get("materia") or "",
        "options": [],
        "answer": None,
        "trap": None,
        "trap_label": None,
    }


def _variants_for_student(seeds, rng, used):
    questions = []
    for seed in seeds:
        bucket = used.setdefault(seed["id"], set())
        variant = vary_question(seed, random.Random(rng.randrange(1, 10**9)), bucket)
        variant.pop("note", None)
        questions.append(variant)
    return questions


def _practice_variants(pool):
    rng = random.Random()
    used = set()
    questions = []
    target = min(8, max(4, len(pool)))
    while len(questions) < target:
        before = len(used)
        variant = vary_question(rng.choice(pool), rng, used)
        variant.pop("note", None)
        questions.append(variant)
        if len(used) == before:
            break
    return questions[:8]


def _latest_for_student(db, group, student_name):
    found = None
    for result in db["results"]:
        if result["group"] == group and result["student_name"] == student_name:
            found = result
    return found


def _new_sheet(
    db,
    group,
    student_name,
    kind,
    questions,
    form_id,
    sheet_format="cerrada",
    materia_label="",
    label="",
):
    sheet_id = _new_id(db["sheets"])
    sheet = {
        "id": sheet_id,
        "form_id": form_id,
        "group": group,
        "student_name": student_name,
        "kind": kind,
        "format": sheet_format,
        "materia_label": materia_label,
        "label": label or student_name,
        "questions": questions,
        "created": _now(),
    }
    db["sheets"][sheet_id] = sheet
    return sheet


def _publish(sheet):
    image = render_sheet(sheet)
    path = SHEETS / f"{sheet['id']}.pdf"
    save_pdf(image, path)
    png = SHEETS / f"{sheet['id']}.png"
    image.save(png)
    return {
        "id": sheet["id"],
        "student_name": sheet["student_name"],
        "group": sheet["group"],
        "kind": sheet["kind"],
        "label": sheet.get("label") or sheet["student_name"],
        "pdf": f"/archivos/{sheet['id']}.pdf",
        "png": f"/archivos/{sheet['id']}.png",
    }
