"""Notas por examen, cuadro por bimestre y resumen del año.

Nota real: puntos obtenidos sobre la nota total que eligió el maestro.
Nota relativa: la misma escala, pero el mejor del examen se lleva la nota total completa.
"""

import csv
import io

TIPOS = {
    "parcial": "Parcial",
    "final": "Examen final",
    "otro": "Actividad",
    "diagnostico": "Diagnóstico",
}
ORDEN_TIPO = {"parcial": 0, "otro": 1, "final": 2, "diagnostico": 3}
BIMESTRES = (1, 2, 3, 4)


def _num(value):
    return round(float(value), 1)


def clean_meta(meta=None):
    """Valida lo que el maestro eligió al crear el examen."""
    meta = dict(meta or {})
    tipo = meta.get("tipo") or "diagnostico"
    if tipo not in TIPOS:
        raise ValueError("Elige si es parcial, examen final, actividad o diagnóstico.")
    try:
        bimestre = int(meta.get("bimestre") or 0)
    except (TypeError, ValueError):
        bimestre = 0
    if tipo == "diagnostico":
        bimestre = bimestre if bimestre in BIMESTRES else 0
    elif bimestre not in BIMESTRES:
        raise ValueError("Elige el bimestre del examen.")
    numero = 0
    if tipo == "parcial":
        try:
            numero = int(meta.get("numero") or 1)
        except (TypeError, ValueError):
            numero = 0
        if not 1 <= numero <= 9:
            raise ValueError("El número de parcial va del 1 al 9.")
    nombre = " ".join(str(meta.get("nombre") or "").split())[:40]
    if tipo == "otro" and len(nombre) < 3:
        raise ValueError("Escribe cómo se llama la actividad, por ejemplo Tarea 2.")
    try:
        nota_total = float(meta.get("nota_total") if meta.get("nota_total") not in (None, "") else 100)
    except (TypeError, ValueError):
        nota_total = 0
    if not 1 <= nota_total <= 100:
        raise ValueError("La nota total debe estar entre 1 y 100.")
    return {
        "tipo": tipo,
        "bimestre": bimestre,
        "numero": numero,
        "nombre": nombre,
        "nota_total": _num(nota_total),
    }


def form_meta(form):
    """Datos del examen aunque sea de una versión anterior sin bimestre ni tipo."""
    tipo = form.get("tipo") or "diagnostico"
    if tipo not in TIPOS:
        tipo = "diagnostico"
    try:
        bimestre = int(form.get("bimestre") or 0)
    except (TypeError, ValueError):
        bimestre = 0
    numero = int(form.get("numero") or 0)
    nombre = (form.get("nombre") or "").strip()
    if tipo == "parcial":
        titulo = f"Parcial {numero or 1}"
    elif tipo == "final":
        titulo = "Examen final"
    elif tipo == "otro":
        titulo = nombre or "Actividad"
    else:
        titulo = nombre or "Diagnóstico"
    nota_total = form.get("nota_total")
    return {
        "id": form["id"],
        "group": form.get("group") or "",
        "created": form.get("created") or "",
        "tipo": tipo,
        "tipo_nombre": TIPOS[tipo],
        "bimestre": bimestre,
        "numero": numero,
        "titulo": titulo,
        "titulo_completo": f"{titulo} · Bimestre {bimestre}" if bimestre else titulo,
        "nota_total": _num(nota_total) if nota_total else 100.0,
        "materias": list(form.get("materias") or []),
        "suma": tipo != "diagnostico" and bimestre in BIMESTRES,
        "apagado": bool(form.get("apagado")),
        "papelera": form.get("papelera") or "",
    }


def sort_key(meta):
    return (meta["bimestre"] or 99, ORDEN_TIPO[meta["tipo"]], meta["numero"], meta["created"])


def latest_by_sheet(db):
    latest = {}
    for result in db.get("results", []):
        if result.get("sheet_id"):
            latest[result["sheet_id"]] = result
    return latest


def exam_rows(db, form, latest=None):
    """Una fila por alumno. Si el examen tiene dos hojas, se suman antes de dar la nota."""
    meta = form_meta(form)
    latest = latest if latest is not None else latest_by_sheet(db)
    people = {}
    for sheet in db["sheets"].values():
        if sheet.get("form_id") == form["id"]:
            people.setdefault(sheet["student_name"], []).append(sheet["id"])
    rows = []
    for name, ids in people.items():
        graded = [latest[sheet_id] for sheet_id in ids if sheet_id in latest]
        score = sum(float(result["score"]) for result in graded)
        total = sum(float(result["total"]) for result in graded)
        complete = len(graded) == len(ids) and total > 0
        rows.append(
            {
                "student_name": name,
                "score": score,
                "total": total,
                "sheets": len(ids),
                "graded": len(graded),
                "state": "listo" if complete else ("parcial" if graded else "pendiente"),
                "nota_real": _num(meta["nota_total"] * score / total) if complete else None,
                "nota_relativa": None,
            }
        )
    best = max((row["nota_real"] for row in rows if row["nota_real"] is not None), default=0)
    for row in rows:
        if row["nota_real"] is None:
            continue
        row["nota_relativa"] = 0.0 if best <= 0 else _num(meta["nota_total"] * row["nota_real"] / best)
    rows.sort(key=lambda row: row["student_name"].lower())
    return meta, rows


def active_forms(db):
    return [form for form in db["forms"].values() if not form.get("papelera")]


def _group_forms(db, group):
    wanted = (group or "").strip().lower()
    return [form for form in active_forms(db) if (form.get("group") or "").strip().lower() == wanted]


def group_materias(db, group):
    """Materias con exámenes en el grupo, para elegir cuál ver."""
    found = set()
    for form in _group_forms(db, group):
        found.update(form.get("materias") or [])
    return sorted(found, key=str.lower)


def _forms_for(db, group, materia=None):
    forms = _group_forms(db, group)
    if materia:
        forms = [form for form in forms if materia in (form.get("materias") or [])]
    return forms


def list_groups(db):
    names = {}
    for name in db.get("groups", {}):
        names.setdefault(name.lower(), name)
    for form in active_forms(db):
        name = (form.get("group") or "").strip()
        if name:
            names.setdefault(name.lower(), name)
    return sorted(names.values(), key=str.lower)


def list_students(db, group):
    """La lista que se guardó en Grupos. Si el grupo es antiguo, la que sale de sus hojas."""
    wanted = (group or "").strip().lower()
    for name, row in db.get("groups", {}).items():
        if name.lower() == wanted and row.get("students"):
            return list(row["students"])
    ids = {form["id"] for form in _group_forms(db, group)}
    names = {}
    for sheet in db["sheets"].values():
        if sheet.get("form_id") in ids:
            names.setdefault(sheet["student_name"].lower(), sheet["student_name"])
    return sorted(names.values(), key=str.lower)


def _sum(values):
    values = [value for value in values if value is not None]
    return _num(sum(values)) if values else None


def grid(db, group, bimestre=None, materia=None):
    """Cuadro tipo Excel: alumnos en filas, exámenes en columnas."""
    latest = latest_by_sheet(db)
    all_forms = _forms_for(db, group, materia)
    available = sorted({form_meta(form)["bimestre"] for form in all_forms})
    tables = []
    for form in all_forms:
        meta, rows = exam_rows(db, form, latest)
        if bimestre is not None and meta["bimestre"] != bimestre:
            continue
        tables.append((meta, {row["student_name"]: row for row in rows}))
    tables.sort(key=lambda item: sort_key(item[0]))
    names = {}
    for _, rows in tables:
        for name in rows:
            names.setdefault(name.lower(), name)
    exams = []
    for meta, rows in tables:
        real = [row["nota_real"] for row in rows.values() if row["nota_real"] is not None]
        relativa = [row["nota_relativa"] for row in rows.values() if row["nota_relativa"] is not None]
        exams.append(
            {
                **meta,
                "calificados": len(real),
                "alumnos": len(rows),
                "promedio_real": _num(sum(real) / len(real)) if real else None,
                "promedio_relativa": _num(sum(relativa) / len(relativa)) if relativa else None,
            }
        )
    students = []
    for name in sorted(names.values(), key=str.lower):
        cells = {}
        counted = []
        for meta, rows in tables:
            row = rows.get(name)
            if row is None:
                continue
            cells[meta["id"]] = {
                "state": row["state"],
                "score": row["score"],
                "total": row["total"],
                "nota_real": row["nota_real"],
                "nota_relativa": row["nota_relativa"],
            }
            if meta["suma"]:
                counted.append(row)
        students.append(
            {
                "student_name": name,
                "cells": cells,
                "total_real": _sum(row["nota_real"] for row in counted),
                "total_relativa": _sum(row["nota_relativa"] for row in counted),
                "faltan": sum(1 for row in counted if row["nota_real"] is None),
                "calificado": any(cell["state"] != "pendiente" for cell in cells.values()),
            }
        )
    return {
        "group": group,
        "materia": materia or "",
        "materias": group_materias(db, group),
        "bimestres": available,
        "exams": exams,
        "students": students,
        "max_total": _num(sum(item["nota_total"] for item in exams if item["suma"])),
    }


def yearly(db, group, materia=None):
    """Zona (parciales y actividades), examen final y total de cada bimestre."""
    latest = latest_by_sheet(db)
    by_bimestre = {number: [] for number in BIMESTRES}
    names = {}
    for form in _forms_for(db, group, materia):
        meta, rows = exam_rows(db, form, latest)
        if not meta["suma"]:
            continue
        by_bimestre[meta["bimestre"]].append((meta, {row["student_name"]: row for row in rows}))
        for row in rows:
            names.setdefault(row["student_name"].lower(), row["student_name"])
    blocks = []
    for number in BIMESTRES:
        items = sorted(by_bimestre[number], key=lambda item: sort_key(item[0]))
        zona = [meta for meta, _ in items if meta["tipo"] != "final"]
        final = [meta for meta, _ in items if meta["tipo"] == "final"]
        blocks.append(
            {
                "n": number,
                "examenes": [
                    {"id": meta["id"], "titulo": meta["titulo"], "nota_total": meta["nota_total"]}
                    for meta, _ in items
                ],
                "max_zona": _num(sum(meta["nota_total"] for meta in zona)) if zona else None,
                "max_final": _num(sum(meta["nota_total"] for meta in final)) if final else None,
                "max_total": _num(sum(meta["nota_total"] for meta, _ in items)) if items else None,
            }
        )
    students = []
    for name in sorted(names.values(), key=str.lower):
        per = []
        for number, block in zip(BIMESTRES, blocks):
            items = sorted(by_bimestre[number], key=lambda item: sort_key(item[0]))
            entry = {"n": number, "hay": bool(items), "faltan": 0}
            for mode in ("real", "relativa"):
                zona_vals, final_vals = [], []
                faltan = 0
                for meta, rows in items:
                    row = rows.get(name)
                    value = row[f"nota_{mode}"] if row else None
                    if value is None:
                        faltan += 1
                    (final_vals if meta["tipo"] == "final" else zona_vals).append(value)
                zona = _sum(zona_vals) if block["max_zona"] is not None else None
                final_note = _sum(final_vals) if block["max_final"] is not None else None
                entry[f"zona_{mode}"] = zona
                entry[f"final_{mode}"] = final_note
                entry[f"total_{mode}"] = _sum([zona, final_note]) if items else None
                entry["faltan"] = faltan
            per.append(entry)
        promedio = {}
        for mode in ("real", "relativa"):
            totals = [entry[f"total_{mode}"] for entry in per if entry["hay"]]
            totals = [value for value in totals if value is not None]
            promedio[mode] = _num(sum(totals) / len(totals)) if totals else None
        students.append(
            {
                "student_name": name,
                "bimestres": per,
                "promedio_real": promedio["real"],
                "promedio_relativa": promedio["relativa"],
            }
        )
    return {
        "group": group,
        "materia": materia or "",
        "materias": group_materias(db, group),
        "bimestres": blocks,
        "students": students,
    }


def _cell(value):
    return "" if value is None else value


def csv_grid(data, modo):
    key = "nota_relativa" if modo == "relativa" else "nota_real"
    total_key = "total_relativa" if modo == "relativa" else "total_real"
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Alumno"] + [f"{exam['titulo_completo']} (de {exam['nota_total']:g})" for exam in data["exams"]] + [f"Total (de {data['max_total']:g})"])
    for student in data["students"]:
        row = [student["student_name"]]
        for exam in data["exams"]:
            cell = student["cells"].get(exam["id"])
            row.append(_cell(cell[key]) if cell else "")
        row.append(_cell(student[total_key]))
        writer.writerow(row)
    return "\ufeff" + out.getvalue()


def csv_yearly(data, modo):
    out = io.StringIO()
    writer = csv.writer(out)
    head = ["Alumno"]
    for block in data["bimestres"]:
        head += [f"B{block['n']} Zona", f"B{block['n']} Final", f"B{block['n']} Total"]
    head.append("Promedio anual")
    writer.writerow(head)
    for student in data["students"]:
        row = [student["student_name"]]
        for entry in student["bimestres"]:
            row += [
                _cell(entry[f"zona_{modo}"]),
                _cell(entry[f"final_{modo}"]),
                _cell(entry[f"total_{modo}"]),
            ]
        row.append(_cell(student[f"promedio_{modo}"]))
        writer.writerow(row)
    return "\ufeff" + out.getvalue()
