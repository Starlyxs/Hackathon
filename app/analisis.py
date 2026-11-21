"""Análisis de un examen: números para los gráficos del grupo y un texto por alumno."""

from app.bank import SKILLS
from app.notas import active_forms, exam_rows, form_meta, latest_by_sheet, sort_key

APRUEBA = 0.6
BUENO = 0.8
FLOJO = 0.6
NIVELES = (
    (0.9, "excelente", "Excelente resultado"),
    (0.75, "bien", "Muy buen resultado"),
    (0.6, "aprobado", "Aprobó"),
    (0.4, "apoyo", "Necesita apoyo"),
    (0.0, "urgente", "Necesita apoyo urgente"),
)


def _level(fraction):
    for floor, key, phrase in NIVELES:
        if fraction >= floor:
            return key, phrase
    return "urgente", NIVELES[-1][2]


def _earned(item):
    weight = float(item.get("puntos") or 1)
    if item.get("format") == "abierta":
        fraction = {"logrado": 1.0, "parcial": 0.5}.get(item.get("status"), 0.0)
    else:
        fraction = 1.0 if item.get("correct") else 0.0
    return weight * fraction, weight


def _topic(item):
    """Tema de la pregunta, o None cuando no dice nada útil (ejercicio suelto o pregunta de una serie escrita)."""
    if item.get("format") == "abierta":
        return None if item.get("serie") else "Interpretación escrita"
    skill = item.get("skill")
    if skill and skill != "general":
        return item.get("skill_name") or SKILLS.get(skill, skill)
    return None


def _bucket(table, name, earned, weight, ok):
    row = table.setdefault(name, {"earned": 0.0, "weight": 0.0, "ok": 0, "n": 0})
    row["earned"] += earned
    row["weight"] += weight
    row["ok"] += 1 if ok else 0
    row["n"] += 1


def _percent(row):
    return round(100 * row["earned"] / row["weight"]) if row["weight"] else 0


def _list_names(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " y " + names[-1]


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


def _student(name, row, items, class_average, previous, intro=None, detail=None, trend=None):
    """Datos y texto de un alumno.

    intro: primera frase cuando el análisis junta varios exámenes.
    detail: [{nombre, pct}] por examen o por materia, para decir en qué le fue mejor y peor.
    trend: (primer %, último %, primer examen, último examen) de una materia en el año.
    """
    topics, series = {}, {}
    blanks = doubtful = 0
    traps = []
    for item in items:
        earned, weight = _earned(item)
        ok = earned >= weight
        topic = _topic(item)
        if topic:
            _bucket(topics, topic, earned, weight, ok)
        if item.get("serie"):
            _bucket(series, item["serie"], earned, weight, ok)
        if item.get("status") == "vacia":
            blanks += 1
        elif item.get("status") == "ambigua":
            doubtful += 1
        label = item.get("trap_label")
        if label and label not in traps:
            traps.append(label)
    done = row["state"] == "listo"
    fraction = (row["score"] / row["total"]) if done and row["total"] else None
    topic_list = sorted(
        ({"nombre": key, "pct": _percent(value), "ok": value["ok"], "n": value["n"]} for key, value in topics.items()),
        key=lambda entry: entry["pct"],
    )
    strong = [entry["nombre"] for entry in topic_list if entry["pct"] >= BUENO * 100][::-1]
    weak = [entry for entry in topic_list if entry["pct"] < FLOJO * 100]
    data = {
        "nombre": name,
        "estado": row["state"],
        "nota": row.get("nota_real"),
        "pct": None if fraction is None else round(fraction * 100),
        "detalle": [{"nombre": entry["nombre"], "pct": entry["pct"]} for entry in (detail or [])],
        "nivel": None,
        "temas": topic_list,
        "series": [{"nombre": key, "pct": _percent(value)} for key, value in series.items()],
        "debilidades": [entry["nombre"] for entry in weak],
        "en_blanco": blanks,
        "dudosas": doubtful,
        "errores": traps[:4],
        "cambio": None,
        "texto": "",
        "refuerzo": False,
    }
    if fraction is None:
        data["texto"] = (
            f"A {name} le falta una hoja por calificar; con las dos se podrá hacer su análisis."
            if row["state"] == "parcial"
            else f"{name} todavía no tiene hoja calificada."
        )
        return data

    level, phrase = _level(fraction)
    data["nivel"] = level
    parts = [intro.replace("{pct}", str(data["pct"])).replace("{phrase}", phrase) if intro else f"{name} sacó {row['nota_real']:g} puntos ({data['pct']}%). {phrase}."]
    if class_average is not None:
        gap = round(100 * fraction) - class_average
        if gap >= 8:
            parts.append(f"Está por encima del promedio del grupo ({class_average}%).")
        elif gap <= -8:
            parts.append(f"Está por debajo del promedio del grupo ({class_average}%).")
        else:
            parts.append(f"Va parecido al promedio del grupo ({class_average}%).")
    if previous is not None:
        diff = data["pct"] - previous["pct"]
        data["cambio"] = diff
        if diff >= 5:
            parts.append(f"Mejoró {diff} puntos porcentuales respecto a {previous['titulo']}.")
        elif diff <= -5:
            parts.append(f"Bajó {-diff} puntos porcentuales respecto a {previous['titulo']}.")
        else:
            parts.append(f"Se mantiene igual que en {previous['titulo']}.")
    trend_said = False
    if trend:
        first, last, first_name, last_name = trend
        if last - first >= 8:
            parts.append(f"Va mejorando: pasó de {first}% en {first_name} a {last}% en {last_name}.")
            trend_said = True
        elif first - last >= 8:
            parts.append(f"Va bajando: pasó de {first}% en {first_name} a {last}% en {last_name}. Conviene hablar con él o ella.")
            trend_said = True
    if detail and len(detail) >= 2 and not trend_said:
        best = max(detail, key=lambda entry: entry["pct"])
        worst = min(detail, key=lambda entry: entry["pct"])
        if best["pct"] - worst["pct"] >= 10:
            parts.append(f"Le fue mejor en {best['nombre']} ({best['pct']}%) y le cuesta más {worst['nombre']} ({worst['pct']}%).")
    if strong:
        parts.append(f"Le fue bien en {_list_names(strong[:3])}.")
    if weak:
        detail = [f"{entry['nombre']} (acertó {entry['ok']} de {entry['n']})" for entry in weak[:3]]
        parts.append(f"Le falta reforzar {_list_names(detail)}.")
    elif fraction < APRUEBA:
        parts.append("Le fue mal en varias partes; conviene repasar lo básico con él o ella.")
    written = [label.split(":", 1)[1].strip().rstrip(". ") for label in traps if label.startswith("no logra interpretar:")]
    errors = [label.rstrip(". ") for label in traps if not label.startswith("no logra interpretar:")]
    if errors:
        parts.append(f"Errores que se notan: {name} " + "; ".join(errors[:3]) + ".")
    if written:
        parts.append("En lo escrito no logró expresar: " + "; ".join(f"«{idea}»" for idea in written[:2]) + ".")
    if blanks:
        parts.append(
            f"Dejó {_plural(blanks, 'pregunta en blanco', 'preguntas en blanco')}: vale la pena preguntarle si no entendió o si le faltó tiempo."
        )
    if doubtful:
        parts.append(f"En {_plural(doubtful, 'pregunta', 'preguntas')} marcó más de una burbuja; recuérdale marcar solo una.")
    if fraction >= 0.9 and not weak:
        parts.append("Sugerencia: darle retos más difíciles o pedirle que apoye a un compañero.")
    elif weak:
        parts.append(f"Sugerencia: una hoja de refuerzo de {weak[0]['nombre']}.")
    elif fraction < APRUEBA:
        parts.append("Sugerencia: una hoja de refuerzo y repasar sus errores con él o ella.")
    data["texto"] = " ".join(parts)
    data["refuerzo"] = bool(weak) or fraction < APRUEBA
    return data


def patterns_from(results):
    """Errores que repite la mitad del grupo o más. results: [{"items": [...]}] uno por alumno."""
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
        messages.append({"percent": percent, "skill_name": bucket["skill_name"], "message": f"El {percent}% de la clase {label}."})
    messages.sort(key=lambda item: item["percent"], reverse=True)
    return messages


def _forms_for_group(db, group):
    wanted = group.strip().lower()
    return [form for form in active_forms(db) if (form.get("group") or "").strip().lower() == wanted]


def _history(db, group, form, latest):
    """Promedio de cada examen de la misma materia del grupo, en orden, y el % de cada alumno."""
    wanted = sorted(form.get("materias") or [])
    entries = []
    for other in _forms_for_group(db, group):
        if sorted(other.get("materias") or []) != wanted:
            continue
        meta, rows = exam_rows(db, other, latest)
        done = [row for row in rows if row["state"] == "listo" and row["total"]]
        if not done:
            continue
        pcts = {row["student_name"]: round(100 * row["score"] / row["total"]) for row in done}
        entries.append(
            {
                "id": other["id"],
                "titulo": meta["titulo_completo"],
                "corto": meta["titulo"],
                "bimestre": meta["bimestre"],
                "promedio": round(sum(pcts.values()) / len(pcts)),
                "alumnos": len(pcts),
                "pcts": pcts,
                "_key": sort_key(meta),
            }
        )
    entries.sort(key=lambda entry: entry["_key"])
    return entries


def build(db, group, form_id=None):
    """Todo lo que necesita la pantalla de análisis para un examen del grupo."""
    latest = latest_by_sheet(db)
    forms = _forms_for_group(db, group)
    graded = [
        form
        for form in forms
        if any(sid in latest and sheet.get("form_id") == form["id"] for sid, sheet in db["sheets"].items())
    ]
    if form_id:
        form = next((item for item in forms if item["id"] == form_id), None)
    else:
        form = max(graded, key=lambda item: item.get("created") or "", default=None)
    if form is None:
        return {"form_id": None, "titulo": "", "hay_datos": False}

    meta, rows = exam_rows(db, form, latest)
    items_by_student = {}
    for sid, sheet in db["sheets"].items():
        if sheet.get("form_id") == form["id"] and sid in latest:
            items_by_student.setdefault(sheet["student_name"], []).extend(latest[sid]["items"])

    done = [row for row in rows if row["state"] == "listo" and row["total"]]
    history = _history(db, group, form, latest)
    position = next((index for index, entry in enumerate(history) if entry["id"] == form["id"]), None)
    previous_entry = history[position - 1] if position else None
    average = round(sum(100 * row["score"] / row["total"] for row in done) / len(done)) if done else None

    students = []
    for row in rows:
        previous = None
        if previous_entry and row["student_name"] in previous_entry["pcts"] and row["state"] == "listo":
            previous = {"pct": previous_entry["pcts"][row["student_name"]], "titulo": previous_entry["titulo"]}
        students.append(_student(row["student_name"], row, items_by_student.get(row["student_name"], []), average, previous))
    students.sort(key=lambda entry: (entry["pct"] is None, -(entry["pct"] or 0), entry["nombre"].lower()))

    topics, series = {}, {}
    for items in items_by_student.values():
        for item in items:
            earned, weight = _earned(item)
            ok = earned >= weight
            topic = _topic(item)
            if topic:
                _bucket(topics, topic, earned, weight, ok)
            if item.get("serie"):
                _bucket(series, item["serie"], earned, weight, ok)
    weak_count = {}
    for entry in students:
        for name in entry["debilidades"]:
            weak_count[name] = weak_count.get(name, 0) + 1

    buckets = [{"desde": low, "hasta": low + 20, "alumnos": 0} for low in (0, 20, 40, 60, 80)]
    for row in done:
        pct = 100 * row["score"] / row["total"]
        buckets[min(4, int(pct // 20))]["alumnos"] += 1
    support = [entry["nombre"] for entry in students if entry["nivel"] in ("apoyo", "urgente")]
    best = max(done, key=lambda row: row["score"] / row["total"], default=None)
    worst = min(done, key=lambda row: row["score"] / row["total"], default=None)
    weakest = min(topics.items(), key=lambda pair: _percent(pair[1]), default=None)
    pending = [row["student_name"] for row in rows if row["state"] != "listo"]

    return {
        "form_id": form["id"],
        "titulo": meta["titulo_completo"],
        "materia": ", ".join(meta["materias"]),
        "nota_total": meta["nota_total"],
        "hay_datos": bool(done),
        "resumen": {
            "calificados": len(done),
            "alumnos": len(rows),
            "pendientes": pending,
            "promedio_pct": average,
            "promedio_nota": round(meta["nota_total"] * average / 100, 1) if average is not None else None,
            "aprueban": sum(1 for row in done if row["score"] / row["total"] >= APRUEBA),
            "apoyo": support,
            "mejor": {"nombre": best["student_name"], "nota": best["nota_real"]} if best else None,
            "menor": {"nombre": worst["student_name"], "nota": worst["nota_real"]} if worst else None,
            "tema_debil": {"nombre": weakest[0], "pct": _percent(weakest[1])} if weakest and _percent(weakest[1]) < 100 else None,
        },
        "distribucion": buckets,
        "temas": sorted(
            ({"nombre": key, "pct": _percent(value), "flojos": weak_count.get(key, 0)} for key, value in topics.items()),
            key=lambda entry: entry["pct"],
        ),
        "series": [{"nombre": key, "pct": _percent(value)} for key, value in series.items()],
        "evolucion": [
            {"titulo": entry["titulo"], "corto": entry["corto"], "promedio": entry["promedio"], "alumnos": entry["alumnos"], "actual": entry["id"] == form["id"]}
            for entry in history
        ],
        "alumnos": students,
        "patrones": patterns_from([{"items": value} for value in items_by_student.values()]),
        "modo": "examen",
        "materias": [],
        "bimestres": [],
    }


def _scope_label(materia):
    return materia or "todas las materias"


def build_scope(db, group, modo, materia=None, bimestre=None):
    """Análisis de varios exámenes juntos: de una materia (modo «materia») o de todas («general»)."""
    latest = latest_by_sheet(db)
    wanted = materia if modo == "materia" else None
    forms = []
    for form in _forms_for_group(db, group):
        meta = form_meta(form)
        if not meta["suma"]:
            continue
        if wanted and wanted not in meta["materias"]:
            continue
        if bimestre and meta["bimestre"] != bimestre:
            continue
        forms.append((meta, form))
    forms.sort(key=lambda pair: sort_key(pair[0]))

    people = {}
    exam_stats = []
    for meta, form in forms:
        _, rows = exam_rows(db, form, latest)
        items_by_student = {}
        for sid, sheet in db["sheets"].items():
            if sheet.get("form_id") == form["id"] and sid in latest:
                items_by_student.setdefault(sheet["student_name"], []).extend(latest[sid]["items"])
        subject = ", ".join(meta["materias"]) or "Sin materia"
        label = meta["titulo"] if wanted else f"{subject} · {meta['titulo']}"
        pcts = []
        for row in rows:
            if row["state"] != "listo" or not row["total"]:
                continue
            fraction = row["score"] / row["total"]
            pcts.append(round(100 * fraction))
            person = people.setdefault(
                row["student_name"], {"earned": 0.0, "total": 0.0, "items": [], "forms": [], "subjects": {}, "terms": {}}
            )
            person["earned"] += meta["nota_total"] * fraction
            person["total"] += meta["nota_total"]
            person["items"].extend(items_by_student.get(row["student_name"], []))
            person["forms"].append({"nombre": label, "pct": round(100 * fraction)})
            for table, key in ((person["subjects"], subject), (person["terms"], meta["bimestre"])):
                pair = table.setdefault(key, [0.0, 0.0])
                pair[0] += meta["nota_total"] * fraction
                pair[1] += meta["nota_total"]
        if pcts:
            exam_stats.append(
                {"titulo": f"{subject} · {meta['titulo_completo']}", "corto": label, "promedio": round(sum(pcts) / len(pcts)), "alumnos": len(pcts), "actual": False}
            )

    title = f"{materia} · todo el año" if wanted else "General · todas las materias"
    if bimestre:
        title = f"{materia} · bimestre {bimestre}" if wanted else f"General · bimestre {bimestre}"
    out = {
        "form_id": None,
        "titulo": title,
        "materia": materia if wanted else "",
        "nota_total": None,
        "hay_datos": bool(people),
        "modo": modo,
        "examenes": len(exam_stats),
    }
    if not people:
        return out

    def pct_of(pair):
        return round(100 * pair[0] / pair[1]) if pair[1] else 0

    class_average = round(100 * sum(p["earned"] / p["total"] for p in people.values()) / len(people))
    students = []
    for name, person in people.items():
        fraction = person["earned"] / person["total"]
        row = {"state": "listo", "score": person["earned"], "total": person["total"], "nota_real": None}
        detail = (
            [{"nombre": key, "pct": pct_of(pair)} for key, pair in person["subjects"].items()]
            if modo == "general"
            else person["forms"]
        )
        trend = None
        if modo == "materia" and len(person["forms"]) >= 2:
            first, last = person["forms"][0], person["forms"][-1]
            trend = (first["pct"], last["pct"], first["nombre"], last["nombre"])
        intro = (
            f"{name} lleva {{pct}}% en {_scope_label(materia if wanted else None)}"
            f" ({_plural(len(person['forms']), 'examen', 'exámenes')}). {{phrase}}."
        )
        entry = _student(name, row, person["items"], class_average, None, intro=intro, detail=detail, trend=trend)
        entry["detalle"] = detail
        entry["examenes"] = len(person["forms"])
        students.append(entry)
    students.sort(key=lambda entry: (-entry["pct"], entry["nombre"].lower()))

    topics, weak_count = {}, {}
    for person in people.values():
        for item in person["items"]:
            earned, weight = _earned(item)
            topic = _topic(item)
            if topic:
                _bucket(topics, topic, earned, weight, earned >= weight)
    for entry in students:
        for topic in entry["debilidades"]:
            weak_count[topic] = weak_count.get(topic, 0) + 1

    buckets = [{"desde": low, "hasta": low + 20, "alumnos": 0} for low in (0, 20, 40, 60, 80)]
    for entry in students:
        buckets[min(4, entry["pct"] // 20)]["alumnos"] += 1

    def group_bars(key):
        """Promedio del grupo por materia o por bimestre: cada alumno cuenta una vez."""
        table = {}
        for person in people.values():
            for name, pair in person[key].items():
                table.setdefault(name, []).append(pct_of(pair))
        return table

    subjects = group_bars("subjects")
    terms = group_bars("terms")
    weakest = min(topics.items(), key=lambda pair: _percent(pair[1]), default=None)
    best, worst = students[0], students[-1]
    out.update(
        {
            "resumen": {
                "calificados": len(students),
                "alumnos": len(students),
                "pendientes": [],
                "promedio_pct": class_average,
                "promedio_nota": None,
                "aprueban": sum(1 for entry in students if entry["pct"] >= APRUEBA * 100),
                "apoyo": [entry["nombre"] for entry in students if entry["nivel"] in ("apoyo", "urgente")],
                "mejor": {"nombre": best["nombre"], "nota": None, "pct": best["pct"]},
                "menor": {"nombre": worst["nombre"], "nota": None, "pct": worst["pct"]},
                "tema_debil": {"nombre": weakest[0], "pct": _percent(weakest[1])} if weakest and _percent(weakest[1]) < 100 else None,
            },
            "distribucion": buckets,
            "temas": sorted(
                ({"nombre": key, "pct": _percent(value), "flojos": weak_count.get(key, 0)} for key, value in topics.items()),
                key=lambda entry: entry["pct"],
            ),
            "series": [],
            "evolucion": exam_stats if modo == "materia" else [],
            "materias": sorted(
                ({"nombre": key, "pct": round(sum(values) / len(values)), "alumnos": len(values), "flojos": sum(1 for value in values if value < 60)} for key, values in subjects.items()),
                key=lambda entry: entry["pct"],
            )
            if modo == "general"
            else [],
            "bimestres": sorted(
                ({"bimestre": key, "pct": round(sum(values) / len(values)), "alumnos": len(values)} for key, values in terms.items()),
                key=lambda entry: entry["bimestre"],
            ),
            "alumnos": students,
            "patrones": patterns_from([{"items": person["items"]} for person in people.values()]),
        }
    )
    return out
