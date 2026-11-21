"""Arma diagnósticos, califica una foto y prepara la hoja de refuerzo."""

import random
import secrets
import time
from datetime import datetime, timezone

from PIL import Image

from app import analisis as analysis
from app.analisis import patterns_from
from app import series as seriesmod
from app.bank import BANK, SKILLS, build_questions
from app.grade import GradeError, read_bubbles, read_photo
from app.materias import ensure_materias
from app.notas import (
    active_forms,
    clean_meta,
    exam_rows,
    form_meta,
    latest_by_sheet,
    list_groups,
    list_students,
    sort_key,
)
from app.render import render_sheet, save_pdf
from app.store import SHEETS, ensure_dirs, last_backup, load, update
from app.variants import vary_question


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(existing):
    while True:
        value = secrets.token_hex(4)
        if value not in existing:
            return value


def _check_duplicate(db, group, info, materias_used):
    """Un mismo examen (por ejemplo Parcial 1 del bimestre 2) se crea una sola vez."""
    if info["tipo"] == "diagnostico":
        return
    wanted = group.strip().lower()
    candidate = form_meta({"id": "nuevo", "group": group, **info})
    for other in active_forms(db):
        if (other.get("group") or "").strip().lower() != wanted:
            continue
        found = form_meta(other)
        if found["tipo"] != candidate["tipo"] or found["bimestre"] != candidate["bimestre"]:
            continue
        if candidate["tipo"] == "parcial" and found["numero"] != candidate["numero"]:
            continue
        if candidate["tipo"] == "otro" and found["titulo"].lower() != candidate["titulo"].lower():
            continue
        if sorted(other.get("materias") or []) != materias_used:
            continue
        where = f" de {', '.join(materias_used)}" if materias_used else ""
        raise ValueError(
            f"Ya existe {candidate['titulo']}{where} del Bimestre {candidate['bimestre']} para {group}. "
            "Búscalo en «Mis exámenes». Si hubo un error, elimínalo ahí y créalo otra vez."
        )


def _canon_group(db, name):
    """«6a» y «6A» son el mismo grupo."""
    name = " ".join((name or "").split())
    for known in list_groups(db):
        if known.lower() == name.lower():
            return known
    return name


def _register_group(db, name, students):
    groups = db.setdefault("groups", {})
    if name not in groups:
        groups[name] = {"name": name, "students": list(students), "created": _now()}
    return groups[name]


def _pick_questions(db, picked, chosen):
    """Las preguntas del examen: las que eligió la maestra, o todas las de las materias marcadas."""
    if picked:
        byid = {row["id"]: row for row in db["authored"]}
        if any(item not in byid for item in picked):
            raise ValueError("Una de las preguntas elegidas ya no existe.")
        rows = [byid[item] for item in picked]
        if chosen:
            outside = [row for row in rows if row.get("materia") not in chosen]
            if outside:
                raise ValueError(f"Este examen es de {', '.join(chosen)}; quita las preguntas de otra materia.")
        return rows
    seeds = list(db["authored"])
    if chosen:
        seeds = [item for item in seeds if item.get("materia") in chosen]
    return seeds


def create_diagnostic(group, names, rng, source="auto", materias=None, meta=None, question_ids=None):
    names = [name.strip() for name in (names or []) if name and name.strip()]
    chosen = [item.strip() for item in (materias or []) if item and item.strip()]
    picked = [item for item in (question_ids or []) if item]
    info = clean_meta(meta)

    def mutate(db):
        nonlocal group, names
        db.setdefault("authored", [])
        ensure_materias(db)
        group = _canon_group(db, group)
        if not group:
            raise ValueError("Elige el grupo.")
        if not names:
            names = list_students(db, group)
        if not names:
            raise ValueError("Este grupo todavía no tiene alumnos. Agrégalos primero en «Grupos».")
        if len(names) > 60:
            raise ValueError("Un grupo admite hasta 60 alumnos.")
        exam = form_meta({"id": "nuevo", "group": group, **info})
        use_authored = bool(picked) or source == "authored" or (source == "auto" and db["authored"])
        if source == "authored" and not db["authored"]:
            raise ValueError("Agrega al menos una pregunta.")
        warnings = []
        shared = None
        closed = []
        opened = []
        if use_authored:
            seeds = _pick_questions(db, picked, chosen)
            closed = [item for item in seeds if item.get("kind", "cerrada") != "abierta"]
            opened = [item for item in seeds if item.get("kind") == "abierta"]
            if picked:
                if len(closed) > 8:
                    raise ValueError(f"Elegiste {len(closed)} preguntas de opciones y la hoja tiene espacio para 8.")
                if len(opened) > 4:
                    raise ValueError(f"Elegiste {len(opened)} preguntas abiertas y la hoja tiene espacio para 4.")
            else:
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
        materias_used = sorted({row["materia"] for row in (closed + opened) if row.get("materia")})
        _check_duplicate(db, group, info, materias_used)
        _register_group(db, group, names)
        form_id = _new_id(db["forms"])
        db["forms"][form_id] = {
            "id": form_id,
            "group": group,
            "kind": "diagnostico",
            "created": _now(),
            "questions": [item["prompt"] for item in (shared or closed or opened)],
            "question_ids": [row["id"] for row in (closed + opened)],
            "materias": materias_used,
            **info,
        }
        extra = {
            "titulo": exam["titulo"],
            "bimestre": info["bimestre"],
            "nota_total": info["nota_total"],
        }
        two = bool(closed and opened)
        created = []
        used = {}
        sheet_ids = []
        for name in names:
            if shared is not None:
                sheet = _new_sheet(db, group, name, "diagnostico", shared, form_id, extra=extra)
                created.append(_publish(sheet))
                sheet_ids.append(sheet["id"])
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
                    extra={**extra, "hoja": "1 de 2"} if two else extra,
                )
                created.append(_publish(sheet))
                sheet_ids.append(sheet["id"])
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
                    extra={**extra, "hoja": "2 de 2"} if two else extra,
                )
                created.append(_publish(sheet))
                sheet_ids.append(sheet["id"])
        pdf = _write_group_pdf(form_id, sheet_ids)
        db["forms"][form_id]["pdf"] = pdf
        return {
            "form_id": form_id,
            "sheets": created,
            "pdf": pdf,
            "titulo": exam["titulo_completo"],
            "nota_total": info["nota_total"],
            "source": "authored" if use_authored else "bank",
            "warning": " ".join(warnings) or None,
        }

    return update(mutate)


def _series_blocks(prepared, rng, used):
    """Las preguntas de un alumno, ya con su número y lo que vale cada una."""
    blocks = []
    number = 0
    for block in prepared:
        questions = []
        for row in block["rows"]:
            if block["tipo"] == "opciones":
                question = _variants_for_student([row], rng, used)[0]
                question["format"] = "cerrada"
                question["materia"] = row.get("materia") or ""
            else:
                question = _open_question(row)
            number += 1
            question["numero"] = number
            question["serie"] = block["nombre"]
            question["puntos"] = round(block["por_pregunta"], 4)
            questions.append(question)
        blocks.append({**{key: block[key] for key in ("nombre", "tipo", "instruccion", "imagen", "puntos", "por_pregunta")}, "preguntas": questions})
    return blocks


def _series_snapshot(prepared):
    return [
        {
            "nombre": block["nombre"],
            "tipo": block["tipo"],
            "instruccion": block["instruccion"],
            "imagen": block["imagen"],
            "puntos": block["puntos"],
            "question_ids": [row["id"] for row in block["rows"]],
        }
        for block in prepared
    ]


def _series_materias(prepared):
    return sorted({row["materia"] for block in prepared for row in block["rows"] if row.get("materia")})


def create_series_exam(group, names, rng, series, materias=None, meta=None):
    """Examen por series: cada serie vale unos puntos que se reparten entre sus preguntas."""
    names = [name.strip() for name in (names or []) if name and name.strip()]
    chosen = [item.strip() for item in (materias or []) if item and item.strip()]
    info = clean_meta(meta)

    def mutate(db):
        nonlocal group, names
        db.setdefault("authored", [])
        ensure_materias(db)
        group = _canon_group(db, group)
        if not group:
            raise ValueError("Elige el grupo.")
        if not names:
            names = list_students(db, group)
        if not names:
            raise ValueError("Este grupo todavía no tiene alumnos. Agrégalos primero en «Grupos».")
        if len(names) > 60:
            raise ValueError("Un grupo admite hasta 60 alumnos.")
        exam = form_meta({"id": "nuevo", "group": group, **info})
        prepared = seriesmod.prepare(db["authored"], series, info["nota_total"], chosen)
        materias_used = _series_materias(prepared)
        _check_duplicate(db, group, info, materias_used)
        _register_group(db, group, names)
        form_id = _new_id(db["forms"])
        db["forms"][form_id] = {
            "id": form_id,
            "group": group,
            "kind": "diagnostico",
            "created": _now(),
            "questions": [row["prompt"] for block in prepared for row in block["rows"]],
            "question_ids": [row["id"] for block in prepared for row in block["rows"]],
            "series": _series_snapshot(prepared),
            "materias": materias_used,
            **info,
        }
        extra = {"titulo": exam["titulo"], "bimestre": info["bimestre"], "nota_total": info["nota_total"]}
        created = []
        used = {}
        sheet_ids = []
        pages_per_student = 1
        for name in names:
            pages = seriesmod.paginate(_series_blocks(prepared, rng, used))
            total = len(pages)
            pages_per_student = max(pages_per_student, total)
            for number, page in enumerate(pages, start=1):
                sheet = _new_sheet(
                    db,
                    group,
                    name,
                    "diagnostico",
                    page["questions"],
                    form_id,
                    sheet_format="series",
                    materia_label=_join_materias(page["questions"]),
                    label=f"{name} · hoja {number} de {total}" if total > 1 else name,
                    extra={**extra, "hoja": f"{number} de {total}" if total > 1 else "", "pagina": number, "layout": page["layout"]},
                )
                created.append(_publish(sheet))
                sheet_ids.append(sheet["id"])
        pdf = _write_group_pdf(form_id, sheet_ids)
        db["forms"][form_id]["pdf"] = pdf
        return {
            "form_id": form_id,
            "sheets": created,
            "pdf": pdf,
            "titulo": exam["titulo_completo"],
            "nota_total": info["nota_total"],
            "source": "series",
            "paginas": pages_per_student,
            "warning": None,
        }

    return update(mutate)


def preview_series_exam(group, names, rng, series, materias=None, meta=None):
    names = [name.strip() for name in (names or []) if name and name.strip()]
    chosen = [item.strip() for item in (materias or []) if item and item.strip()]
    info = clean_meta(meta)
    db = load()
    ensure_materias(db)
    group = _canon_group(db, group) or "Grupo"
    exam = form_meta({"id": "vista", "group": group, **info})
    roster = names or list_students(db, group)
    name = roster[0] if roster else "Nombre del alumno"
    prepared = seriesmod.prepare(db.get("authored", []), series, info["nota_total"], chosen)
    pages = seriesmod.paginate(_series_blocks(prepared, rng, {}))
    ensure_dirs()
    stamp = int(time.time())
    urls = []
    for number, page in enumerate(pages, start=1):
        sheet = {
            "id": "vista",
            "student_name": name,
            "group": group,
            "kind": "diagnostico",
            "format": "series",
            "materia_label": _join_materias(page["questions"]),
            "questions": page["questions"],
            "layout": page["layout"],
            "titulo": exam["titulo"],
            "bimestre": info["bimestre"],
            "nota_total": info["nota_total"],
            "hoja": f"{number} de {len(pages)}" if len(pages) > 1 else "",
        }
        render_sheet(sheet).save(SHEETS / f"vista-previa-{number}.png")
        urls.append(f"/archivos/vista-previa-{number}.png?v={stamp}")
    return {"png": urls[0], "pngs": urls, "student_name": name}


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


def check_sheet(db, sheet, form_id=None):
    """La hoja debe ser de un examen encendido y, si la maestra eligió uno, de ese examen."""
    form = db["forms"].get(sheet.get("form_id") or "")
    if form is not None:
        title = form_meta(form)["titulo_completo"]
        if form.get("papelera"):
            raise GradeError(f"{title} está en la papelera. Restáuralo en Exámenes para calificarlo.")
        if form.get("apagado"):
            raise GradeError(f"{title} está apagado. Enciéndelo en Exámenes para seguir calificando.")
    if form_id and (form is None or form["id"] != form_id):
        name = form_meta(form)["titulo_completo"] if form else "refuerzo"
        raise GradeError(f"Esa hoja es de «{name}», no del examen que estás calificando.")
    return form


def sheet_status(sheet_id, form_id=None):
    """Respuesta rápida para la cámara en vivo: de quién es la hoja y si se puede calificar."""
    db = load()
    sheet = db["sheets"].get(sheet_id)
    if sheet is None:
        return {"ok": False, "mensaje": "Ese QR no es de esta laptop."}
    try:
        check_sheet(db, sheet, form_id)
    except GradeError as exc:
        return {"ok": False, "student_name": sheet["student_name"], "mensaje": str(exc)}
    return {"ok": True, "sheet_id": sheet_id, "student_name": sheet["student_name"], "hoja": sheet.get("hoja") or ""}


def grade_photo(image_bgr, form_id=None):
    aligned, sheet_id = read_photo(image_bgr)
    return grade_aligned(aligned, sheet_id, form_id)


def grade_aligned(aligned, sheet_id, form_id=None):
    """Califica una hoja que ya se leyó y se enderezó (de la cámara, de una foto o de un PDF)."""
    db = load()
    preview = db.get("sheets", {}).get(sheet_id)
    if preview is None:
        raise GradeError("Ese QR no está en esta laptop. Genera la hoja desde aquí antes de calificarla.")
    check_sheet(db, preview, form_id)
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

    if preview.get("format") == "series":
        return update(lambda db: _grade_series_page(db, sheet_id, aligned))

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


def review_payload(sheet, pending):
    """Lo que la maestra debe revisar de una hoja con preguntas escritas."""
    written = [question for question in sheet["questions"] if question.get("format") == "abierta"]
    closed = pending["items"]
    return {
        "needs_review": True,
        "sheet_id": sheet["id"],
        "student_name": sheet["student_name"],
        "group": sheet["group"],
        "hoja": sheet.get("hoja") or "",
        "items": [
            {
                "prompt": question["prompt"],
                "criterion": question.get("criterion") or "",
                "materia": question.get("materia") or "",
                "puntos": question["puntos"],
                "serie": question.get("serie") or "",
            }
            for question in written
        ],
        "opciones": {
            "bien": sum(1 for item in closed if item.get("correct")),
            "total": len(closed),
            "puntos": round(float(pending["score"]), 4),
        },
    }


def _grade_series_page(db, sheet_id, aligned):
    """Lee las burbujas de una hoja por series. Si trae preguntas escritas, deja las burbujas
    pendientes y pide a la maestra que marque lo escrito."""
    sheet = db["sheets"].get(sheet_id)
    if sheet is None:
        raise GradeError("Ese QR no está en esta laptop. Genera la hoja desde aquí antes de calificarla.")
    closed = [question for question in sheet["questions"] if question.get("format") != "abierta"]
    written = [question for question in sheet["questions"] if question.get("format") == "abierta"]
    choices, details = read_bubbles(aligned, seriesmod.bubble_slots(sheet)) if closed else ([], [])
    items = []
    score = 0.0
    right = 0
    for question, choice, detail in zip(closed, choices, details):
        correct = choice is not None and choice == question["answer"]
        if correct:
            score += question["puntos"]
            right += 1
        trap = question.get("trap") is not None and choice is not None and choice == question["trap"] and not correct
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
                "puntos": question["puntos"],
                "serie": question.get("serie") or "",
                "trap": trap,
                "trap_label": question.get("trap_label") if trap else None,
            }
        )
    if written:
        pending = {"items": items, "score": round(score, 4), "created": _now()}
        db.setdefault("pending", {})[sheet_id] = pending
        return review_payload(sheet, pending)
    result = {
        "sheet_id": sheet_id,
        "student_name": sheet["student_name"],
        "group": sheet["group"],
        "kind": sheet["kind"],
        "score": round(score, 4),
        "total": round(sum(question["puntos"] for question in sheet["questions"]), 4),
        "items": items,
        "created": _now(),
    }
    db["results"].append(result)
    return result


def _save_series_interpretation(db, sheet, marks, points):
    written = [question for question in sheet["questions"] if question.get("format") == "abierta"]
    if not written:
        raise ValueError("Esa hoja no tiene preguntas escritas.")
    pending = (db.get("pending") or {}).get(sheet["id"])
    if pending is None:
        raise ValueError("Vuelve a escanear la hoja antes de guardar lo escrito.")
    if len(marks) != len(written):
        raise ValueError("Falta calificar una respuesta.")
    items = list(pending["items"])
    score = float(pending["score"])
    for question, mark in zip(written, marks):
        if mark not in points:
            raise ValueError("Marca cada respuesta como logrado, parcial o aún no.")
        score += question["puntos"] * points[mark]
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
                "puntos": question["puntos"],
                "serie": question.get("serie") or "",
                "trap": mark == "aun_no",
                "trap_label": f"no logra interpretar: {criterion[:90]}" if mark == "aun_no" else None,
            }
        )
    result = {
        "sheet_id": sheet["id"],
        "student_name": sheet["student_name"],
        "group": sheet["group"],
        "kind": sheet["kind"],
        "score": round(score, 4),
        "total": round(sum(question["puntos"] for question in sheet["questions"]), 4),
        "items": items,
        "created": _now(),
    }
    db["pending"].pop(sheet["id"], None)
    db["results"].append(result)
    return result


def save_interpretation(sheet_id, marks):
    points = {"logrado": 1, "parcial": 0.5, "aun_no": 0}

    def mutate(db):
        sheet = db["sheets"].get(sheet_id)
        if sheet is not None and sheet.get("format") == "series":
            return _save_series_interpretation(db, sheet, marks, points)
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


def exam_summary(sheet_id):
    """Qué examen es esta hoja y cuánto lleva el alumno en él."""
    db = load()
    sheet = db["sheets"].get(sheet_id)
    form = db["forms"].get(sheet.get("form_id")) if sheet else None
    if form is None:
        return None
    meta, rows = exam_rows(db, form)
    mine = next((row for row in rows if row["student_name"] == sheet["student_name"]), None)
    return {
        "form_id": form["id"],
        "titulo": meta["titulo_completo"],
        "nota_total": meta["nota_total"],
        "nota_real": mine["nota_real"] if mine else None,
        "nota_relativa": mine["nota_relativa"] if mine else None,
        "state": mine["state"] if mine else "pendiente",
    }


def _form_or_fail(db, form_id):
    form = db["forms"].get(form_id)
    if form is None:
        raise ValueError("Ese examen ya no existe.")
    return form


def trash_exam(form_id):
    """Eliminar manda el examen a la papelera. Se puede restaurar."""

    def mutate(db):
        _form_or_fail(db, form_id)["papelera"] = _now()
        return {"ok": True}

    return update(mutate)


delete_exam = trash_exam


def restore_exam(form_id):
    def mutate(db):
        form = _form_or_fail(db, form_id)
        if form.get("papelera"):
            info = {key: form.get(key) for key in ("tipo", "bimestre", "numero", "nombre", "nota_total")}
            _check_duplicate(db, form.get("group") or "", info, sorted(form.get("materias") or []))
        form.pop("papelera", None)
        _group_rows(db)
        name = (form.get("group") or "").strip()
        if name and name.lower() not in {key.lower() for key in db["groups"]}:
            students = sorted(
                {sheet["student_name"] for sheet in db["sheets"].values() if sheet.get("form_id") == form["id"]},
                key=str.lower,
            )
            _register_group(db, name, students)
        return {"ok": True}

    return update(mutate)


def set_exam_off(form_id, off):
    """Un examen apagado ya no recibe hojas, pero conserva sus notas."""

    def mutate(db):
        form = _form_or_fail(db, form_id)
        form["apagado"] = bool(off)
        return {"ok": True, "apagado": bool(off)}

    return update(mutate)


def purge_exam(form_id):
    """Borra el examen, sus hojas y sus notas para siempre."""

    def mutate(db):
        _form_or_fail(db, form_id)
        db["forms"].pop(form_id)
        ids = {sid for sid, sheet in db["sheets"].items() if sheet.get("form_id") == form_id}
        for sid in ids:
            db["sheets"].pop(sid, None)
        db["results"] = [row for row in db["results"] if row.get("sheet_id") not in ids]
        for sid in ids:
            (db.get("pending") or {}).pop(sid, None)
        files = [SHEETS / f"{sid}.{ext}" for sid in ids for ext in ("png", "pdf")]
        files += [SHEETS / "escaneos" / f"{sid}.jpg" for sid in ids]
        files.append(SHEETS / f"{form_id}-grupo.pdf")
        for path in files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return {"ok": True}

    return update(mutate)


def _group_rows(db):
    """Lista de grupos. Los grupos de versiones anteriores se registran aquí la primera vez."""
    registry = db.setdefault("groups", {})
    if not db.get("groups_migrated"):
        # Solo una vez: así un grupo que se elimina no vuelve a aparecer.
        known = {name.lower() for name in registry}
        for form in db["forms"].values():
            name = (form.get("group") or "").strip()
            if name and name.lower() not in known:
                students = sorted(
                    {sheet["student_name"] for sheet in db["sheets"].values() if sheet.get("form_id") == form["id"]},
                    key=str.lower,
                )
                registry[name] = {"name": name, "students": students, "created": form.get("created") or _now()}
                known.add(name.lower())
        db["groups_migrated"] = True
    rows = []
    for name in sorted(registry, key=str.lower):
        exams = [f for f in active_forms(db) if (f.get("group") or "").strip().lower() == name.lower()]
        rows.append({"name": name, "students": list(registry[name].get("students") or []), "exams": len(exams)})
    return rows


def list_my_groups():
    return update(lambda db: {"groups": _group_rows(db)})


def save_group(name, students):
    name = " ".join((name or "").split())
    if not 1 <= len(name) <= 40:
        raise ValueError("Escribe el nombre del grupo, por ejemplo 6A.")
    clean, seen = [], set()
    for item in students or []:
        item = " ".join(str(item).split())[:80]
        if item and item.lower() not in seen:
            seen.add(item.lower())
            clean.append(item)
    if len(clean) > 60:
        raise ValueError("Un grupo admite hasta 60 alumnos.")

    def mutate(db):
        _group_rows(db)
        key = _canon_group(db, name)
        created = (db["groups"].get(key) or {}).get("created") or _now()
        db["groups"][key] = {"name": key, "students": clean, "created": created}
        return {"ok": True, "name": key, "students": clean}

    return update(mutate)


def delete_group(name):
    def mutate(db):
        _group_rows(db)
        key = _canon_group(db, name)
        # Sus exámenes van a la papelera con sus notas; se pueden restaurar.
        moved = [f for f in active_forms(db) if (f.get("group") or "").strip().lower() == key.lower()]
        for form in moved:
            form["papelera"] = _now()
        for stored in [n for n in db["groups"] if n.lower() == key.lower()]:
            db["groups"].pop(stored, None)
        return {"ok": True, "examenes": len(moved)}

    return update(mutate)


def overview():
    """Lo que ya hay y cuál es el siguiente paso."""

    def read(db):
        rows = _group_rows(db)
        students = sum(len(row["students"]) for row in rows)
        questions = len(db.get("authored") or [])
        latest = latest_by_sheet(db)
        exams = active_forms(db)
        pending, pending_titles = 0, []
        for form in exams:
            if form.get("apagado"):
                continue
            meta, grades = exam_rows(db, form, latest)
            missing = sum(1 for row in grades if row["state"] != "listo")
            if missing:
                pending += missing
                pending_titles.append(f"{meta['titulo_completo']} ({meta['group']})")
        if not rows or students == 0:
            step = {"paso": "grupos", "texto": "Empieza creando tu grupo y poniendo la lista de alumnos.", "enlace": "/grupos", "boton": "Crear mi grupo"}
        elif not exams:
            step = {"paso": "examenes", "texto": "Crea tu primer examen: elige el bimestre, si es parcial o final, la nota total y escribe sus preguntas.", "enlace": "/examenes", "boton": "Crear un examen"}
        elif pending:
            where = ", ".join(pending_titles[:2]) + ("…" if len(pending_titles) > 2 else "")
            step = {"paso": "calificar", "texto": f"Quedan {pending} alumnos por calificar en {where}.", "enlace": "/calificar", "boton": "Subir hojas escaneadas"}
        else:
            step = {"paso": "notas", "texto": "Todo está calificado. Revisa las notas del año.", "enlace": "/notas", "boton": "Ver notas del año"}
        return {
            "siguiente": step,
            "grupos": len(rows),
            "alumnos": students,
            "preguntas": questions,
            "examenes": len(exams),
            "apagados": sum(1 for form in exams if form.get("apagado")),
            "pendientes": pending,
            "copia": last_backup(),
        }

    return update(read)


def _write_group_pdf(form_id, sheet_ids):
    pages = []
    for sheet_id in sheet_ids:
        path = SHEETS / f"{sheet_id}.png"
        if path.exists():
            pages.append(Image.open(path).convert("RGB"))
    if not pages:
        return None
    out = SHEETS / f"{form_id}-grupo.pdf"
    pages[0].save(out, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    for page in pages:
        page.close()
    return f"/archivos/{form_id}-grupo.pdf"


def list_exams():
    def read(db):
        latest = latest_by_sheet(db)
        exams = []
        trash = []
        for form in db.get("forms", {}).values():
            if form.get("papelera"):
                meta = form_meta(form)
                trash.append({"id": form["id"], "titulo_completo": meta["titulo_completo"], "group": meta["group"], "papelera": form["papelera"]})
                continue
            sheets = [sheet for sheet in db["sheets"].values() if sheet.get("form_id") == form["id"]]
            sheets.sort(key=lambda sheet: (sheet["student_name"], sheet.get("format") == "abierta", sheet.get("pagina", 0)))
            sheet_ids = [sheet["id"] for sheet in sheets]
            pdf = form.get("pdf")
            if not pdf and sheet_ids:
                pdf = _write_group_pdf(form["id"], sheet_ids)
                form["pdf"] = pdf
            meta, rows = exam_rows(db, form, latest)
            exams.append(
                {
                    **meta,
                    "students": sorted({sheet["student_name"] for sheet in sheets}),
                    "question_ids": list(form.get("question_ids") or []),
                    "series": [
                        {
                            "nombre": item["nombre"],
                            "tipo": item["tipo"],
                            "puntos": item["puntos"],
                            "preguntas": len(item["question_ids"]),
                        }
                        for item in (form.get("series") or [])
                    ],
                    "pdf": pdf,
                    "preview": f"/archivos/{sheets[0]['id']}.png" if sheets else None,
                    "grades": rows,
                    "calificados": sum(1 for row in rows if row["state"] == "listo"),
                }
            )
        exams.sort(key=lambda exam: (exam["group"].lower(),) + sort_key(exam))
        trash.sort(key=lambda item: item["papelera"], reverse=True)
        return {"exams": exams, "trash": trash, "groups": list_groups(db)}

    return update(read)


def groups_and_students(group=None):
    db = load()
    return {"groups": list_groups(db), "students": list_students(db, group) if group else []}


def preview_diagnostic(group, names, rng, materias=None, meta=None, question_ids=None):
    names = [name.strip() for name in (names or []) if name and name.strip()]
    chosen = [item.strip() for item in (materias or []) if item and item.strip()]
    picked = [item for item in (question_ids or []) if item]
    info = clean_meta(meta)
    db = load()
    ensure_materias(db)
    group = _canon_group(db, group) or "Grupo"
    exam = form_meta({"id": "vista", "group": group, **info})
    roster = names or list_students(db, group)
    name = roster[0] if roster else "Nombre del alumno"
    if db.get("authored") or picked:
        seeds = _pick_questions(db, picked, chosen)
        closed = [item for item in seeds if item.get("kind", "cerrada") != "abierta"][:8]
        opened = [item for item in seeds if item.get("kind") == "abierta"][:4]
        if not closed and not opened:
            raise ValueError("No hay preguntas en las materias elegidas.")
        if closed:
            questions = _variants_for_student(closed, rng, {})
            sheet_format = "cerrada"
            label = _join_materias(closed)
        else:
            questions = [_open_question(item) for item in opened]
            sheet_format = "abierta"
            label = _join_materias(opened)
    else:
        questions = build_questions(rng)
        sheet_format = "cerrada"
        label = "Diagnóstico de ejemplo"
    sheet = {
        "id": "vista",
        "student_name": name,
        "group": group,
        "kind": "diagnostico",
        "format": sheet_format,
        "materia_label": label,
        "questions": questions,
        "titulo": exam["titulo"],
        "bimestre": info["bimestre"],
        "nota_total": info["nota_total"],
    }
    image = render_sheet(sheet)
    ensure_dirs()
    image.save(SHEETS / "vista-previa.png")
    return {"png": f"/archivos/vista-previa.png?v={int(time.time())}", "student_name": name}


def class_report(group, form_id=None):
    """Patrón de errores de un examen. Sin form_id, el último examen del grupo con hojas calificadas."""
    db = load()
    latest = latest_by_sheet(db)
    wanted = group.strip().lower()
    forms = [form for form in active_forms(db) if (form.get("group") or "").strip().lower() == wanted]
    graded_forms = [
        form
        for form in forms
        if any(sid in latest and sheet.get("form_id") == form["id"] for sid, sheet in db["sheets"].items())
    ]
    if form_id:
        form = next((item for item in forms if item["id"] == form_id), None)
    else:
        form = max(graded_forms, key=lambda item: item.get("created") or "", default=None)
    if form is None:
        return {"students": 0, "results": [], "patterns": [], "form_id": None, "titulo": ""}
    meta, rows = exam_rows(db, form, latest)
    per_student = {}
    for sid, sheet in db["sheets"].items():
        if sheet.get("form_id") == form["id"] and sid in latest:
            bucket = per_student.setdefault(sheet["student_name"], {"items": []})
            bucket["items"].extend(latest[sid]["items"])
    return {
        "students": len(per_student),
        "results": rows,
        "patterns": patterns_from(list(per_student.values())),
        "form_id": form["id"],
        "titulo": meta["titulo_completo"],
    }


def class_analysis(group, form_id=None, modo="examen", materia=None, bimestre=None):
    """Gráficos del grupo y texto por alumno: de un examen, de una materia o de todo el grupo."""
    db = load()
    if modo in ("materia", "general"):
        try:
            term = int(bimestre) if bimestre else None
        except (TypeError, ValueError):
            term = None
        return analysis.build_scope(db, group.strip(), modo, (materia or "").strip() or None, term)
    return analysis.build(db, group.strip(), form_id or None)


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
    extra=None,
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
        **(extra or {}),
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
