"""Revisar y corregir hojas ya leídas: ninguna cámara ni escáner acierta el 100 %.

La maestra ve la hoja escaneada, compara con lo que leyó el programa y cambia la respuesta
de una burbuja si hace falta. La nota se vuelve a calcular y queda como la nota vigente."""

from app.bank import SKILLS
from app.escaneo import scan_url
from app.notas import latest_by_sheet
from app.service import _now
from app.store import load, update

DOUBT = ("vacia", "ambigua")
STATUS_TEXT = {
    "marcada": "",
    "vacia": "Sin marca",
    "ambigua": "Dos marcas",
    "corregida": "Corregida",
}
POINTS = {"logrado": 1, "parcial": 0.5, "aun_no": 0}


def _base(db, sheet_id):
    """Último resultado de la hoja o, si espera revisión de lo escrito, lo leído hasta ahora."""
    pending = (db.get("pending") or {}).get(sheet_id)
    if pending is not None:
        return pending, "pendiente"
    latest = latest_by_sheet(db).get(sheet_id)
    if latest is not None:
        return latest, "calificada"
    return None, "sin_calificar"


def _closed_questions(sheet):
    return [question for question in sheet["questions"] if question.get("format") != "abierta"]


def list_sheets(form_id):
    """Las hojas de un examen con cuántas respuestas dudosas tiene cada una."""
    db = load()
    rows = []
    for sheet in db["sheets"].values():
        if sheet.get("form_id") != form_id:
            continue
        base, state = _base(db, sheet["id"])
        doubtful = 0
        if base is not None:
            doubtful = sum(1 for item in base["items"] if item.get("format") != "abierta" and item.get("status") in DOUBT)
        rows.append(
            {
                "sheet_id": sheet["id"],
                "alumno": sheet["student_name"],
                "hoja": sheet.get("hoja") or "",
                "pagina": sheet.get("pagina") or 1,
                "estado": state,
                "dudosas": doubtful,
                "editable": sheet.get("format") in ("series", "cerrada"),
                "imagen": scan_url(sheet["id"]),
            }
        )
    rows.sort(key=lambda row: (-row["dudosas"], row["alumno"].lower(), row["pagina"]))
    return rows


def detail(sheet_id):
    db = load()
    sheet = db["sheets"].get(sheet_id)
    if sheet is None:
        raise ValueError("Esa hoja ya no existe.")
    if sheet.get("format") not in ("series", "cerrada"):
        raise ValueError("Esta hoja no tiene burbujas para corregir.")
    base, state = _base(db, sheet_id)
    if base is None:
        raise ValueError("Esa hoja todavía no se ha calificado.")
    closed = _closed_questions(sheet)
    items = [item for item in base["items"] if item.get("format") != "abierta"]
    written = [item for item in base["items"] if item.get("format") == "abierta"]
    questions = []
    for number, (question, item) in enumerate(zip(closed, items), start=1):
        questions.append(
            {
                "numero": number,
                "prompt": question["prompt"],
                "options": list(question["options"]),
                "serie": question.get("serie") or "",
                "puntos": question.get("puntos"),
                "choice": item.get("choice"),
                "status": item.get("status") or "marcada",
                "aviso": STATUS_TEXT.get(item.get("status") or "marcada", ""),
                "answer": item.get("answer"),
            }
        )
    return {
        "sheet_id": sheet_id,
        "alumno": sheet["student_name"],
        "hoja": sheet.get("hoja") or "",
        "estado": state,
        "preguntas": questions,
        "escritas": [{"prompt": item["prompt"], "status": item.get("status"), "puntos": item.get("puntos")} for item in written],
        "imagen": scan_url(sheet_id),
        "score": base["score"] if state == "calificada" else None,
        "total": base.get("total"),
    }


def _item(question, choice, status, series):
    correct = choice is not None and choice == question["answer"]
    trap = question.get("trap") is not None and choice is not None and choice == question["trap"] and not correct
    item = {
        "prompt": question["prompt"],
        "skill": question["skill"],
        "skill_name": SKILLS.get(question["skill"], question["skill"]),
        "choice": choice,
        "answer": question["answer"],
        "correct": correct,
        "status": status,
        "format": "cerrada",
        "trap": trap,
        "trap_label": question.get("trap_label") if trap else None,
    }
    if series:
        item["puntos"] = question["puntos"]
        item["serie"] = question.get("serie") or ""
    return item


def fix(sheet_id, choices):
    """choices: una entrada por pregunta de opciones, con 0-3 o None (en blanco)."""

    def mutate(db):
        sheet = db["sheets"].get(sheet_id)
        if sheet is None or sheet.get("format") not in ("series", "cerrada"):
            raise ValueError("Esa hoja no se puede corregir.")
        base, state = _base(db, sheet_id)
        if base is None:
            raise ValueError("Esa hoja todavía no se ha calificado.")
        closed = _closed_questions(sheet)
        if len(choices) != len(closed):
            raise ValueError("Falta una respuesta por corregir.")
        series = sheet.get("format") == "series"
        old = [item for item in base["items"] if item.get("format") != "abierta"]
        written = [item for item in base["items"] if item.get("format") == "abierta"]
        items = []
        score = 0.0
        for question, choice, before in zip(closed, choices, old):
            if choice is not None and choice not in (0, 1, 2, 3):
                raise ValueError("Una respuesta no es válida.")
            status = before.get("status") or "marcada"
            if choice != before.get("choice"):
                status = "corregida"
            item = _item(question, choice, status, series)
            if item["correct"]:
                score += question["puntos"] if series else 1
            items.append(item)
        if state == "pendiente":
            base["items"] = items
            base["score"] = round(score, 4)
            return {"ok": True, "estado": state}
        for item in written:
            score += (item.get("puntos") or 0) * POINTS.get(item.get("status"), 0)
        result = {
            "sheet_id": sheet_id,
            "student_name": sheet["student_name"],
            "group": sheet["group"],
            "kind": sheet["kind"],
            "score": round(score, 4),
            "total": round(sum(question["puntos"] for question in sheet["questions"]), 4) if series else len(items),
            "items": items + written,
            "created": _now(),
            "corregida": True,
        }
        db["results"].append(result)
        return {"ok": True, "estado": state, "score": result["score"], "total": result["total"]}

    return update(mutate)
