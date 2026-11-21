"""Boletín por alumno: notas del año por materia y un texto de cómo va y qué reforzar."""

from datetime import date

from app import analisis
from app.notas import group_materias, list_students, yearly
from app.store import load


def _grade(value):
    return None if value is None else round(float(value), 1)


def build(group, student=None):
    db = load()
    names = list_students(db, group)
    if not names:
        raise ValueError("Ese grupo no tiene alumnos.")
    if student:
        names = [name for name in names if name.lower() == student.strip().lower()]
        if not names:
            raise ValueError("Ese alumno no está en el grupo.")
    subjects = group_materias(db, group)
    tables = {}
    for subject in subjects:
        data = yearly(db, group, subject)
        tables[subject] = {
            "maximos": [block["max_total"] for block in data["bimestres"]],
            "alumnos": {row["student_name"]: row for row in data["students"]},
        }
    general = analisis.build_scope(db, group, "general", None, None)
    texts = {row["nombre"]: row for row in general.get("alumnos") or []}
    cards = []
    for name in names:
        rows = []
        for subject in subjects:
            table = tables[subject]
            mine = table["alumnos"].get(name)
            if mine is None:
                continue
            terms = [
                {"n": entry["n"], "nota": _grade(entry["total_real"]), "max": _grade(maximum), "faltan": entry["faltan"]}
                for entry, maximum in zip(mine["bimestres"], table["maximos"])
            ]
            done = [term for term in terms if term["nota"] is not None and term["max"]]
            total = sum(term["nota"] for term in done)
            maximum = sum(term["max"] for term in done)
            rows.append(
                {
                    "materia": subject,
                    "bimestres": terms,
                    "total": _grade(total) if done else None,
                    "max": _grade(maximum) if done else None,
                    "pct": round(100 * total / maximum) if done and maximum else None,
                }
            )
        person = texts.get(name)
        cards.append(
            {
                "alumno": name,
                "materias": rows,
                "pct": person["pct"] if person else None,
                "nivel": person["nivel"] if person else None,
                "texto": person["texto"] if person else "Todavía no hay exámenes calificados para este alumno.",
                "reforzar": person["debilidades"] if person else [],
            }
        )
    return {"group": group, "fecha": date.today().isoformat(), "alumnos": cards}
