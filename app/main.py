"""Servidor local. Se abre en el navegador de la misma laptop."""

import random
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.demo import simulate_class
from app.grade import GradeError
from app.notas import csv_grid, csv_yearly, grid, yearly
from app.service import (
    add_materia,
    add_question,
    class_report,
    create_diagnostic,
    create_reinforcement,
    delete_exam,
    delete_question,
    exam_summary,
    grade_photo,
    groups_and_students,
    list_exams,
    list_questions,
    preview_diagnostic,
    save_interpretation,
)
from app.store import SHEETS, ensure_dirs, load
from app.variants import preview_variants

ensure_dirs()
STATIC = Path(__file__).resolve().parent / "static"
STATIC.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Hojas en papel")
app.mount("/archivos", StaticFiles(directory=str(SHEETS)), name="archivos")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

PASOS = (
    ("preguntas", "/preguntas", "1. Preguntas"),
    ("examenes", "/examenes", "2. Exámenes"),
    ("calificar", "/", "3. Calificar"),
    ("notas", "/notas", "4. Notas del año"),
)


def html_page(name, active=""):
    path = Path(__file__).parent / "templates" / name
    links = ""
    for key, href, label in PASOS:
        mark = ' class="active"' if key == active else ""
        links += f'<a href="{href}"{mark}>{label}</a>'
    html = path.read_text(encoding="utf-8").replace("<!--NAV-->", f"<nav>{links}</nav>")
    return HTMLResponse(html)


class DiagnosticIn(BaseModel):
    group: str = Field(min_length=1, max_length=40)
    names: list[str]
    materias: list[str] = []
    bimestre: int = 1
    tipo: str = "parcial"
    numero: int = 1
    nombre: str = ""
    nota_total: float = 20

    def meta(self):
        return {
            "bimestre": self.bimestre,
            "tipo": self.tipo,
            "numero": self.numero,
            "nombre": self.nombre,
            "nota_total": self.nota_total,
        }


class QuestionIn(BaseModel):
    prompt: str = Field(min_length=8, max_length=220)
    answer: str = ""
    criterion: str = ""
    skill: str = "general"
    materia: str = "Matemática"
    kind: str = "cerrada"


class MateriaIn(BaseModel):
    name: str = Field(min_length=3, max_length=48)


class InterpretIn(BaseModel):
    sheet_id: str = Field(min_length=4, max_length=20)
    marks: list[str]


class ReinforceIn(BaseModel):
    group: str = Field(min_length=1, max_length=40)
    student_name: str = Field(min_length=1, max_length=80)


class SimulateIn(BaseModel):
    group: str = Field(default="6A", min_length=1, max_length=40)


def with_context(result):
    """Añade a la respuesta de una hoja calificada el examen al que pertenece y el patrón de ese examen."""
    exam = exam_summary(result["sheet_id"])
    result["exam"] = exam
    report = class_report(result["group"], exam["form_id"] if exam else None)
    result["patterns"] = report["patterns"]
    return result


@app.get("/")
def home():
    return html_page("index.html", "calificar")


@app.get("/preguntas")
def questions_page():
    return html_page("preguntas.html", "preguntas")


@app.get("/examenes")
def exams_page():
    return html_page("examenes.html", "examenes")


@app.get("/notas")
def notes_page():
    return html_page("notas.html", "notas")


@app.get("/api/examenes")
def get_exams():
    return list_exams()


@app.post("/api/vista-examen")
def post_exam_preview(body: DiagnosticIn):
    names = [name.strip() for name in body.names if name.strip()]
    if not names:
        raise HTTPException(400, "Escribe al menos un nombre para la vista previa.")
    try:
        return preview_diagnostic(body.group.strip(), names, random.Random(), materias=body.materias, meta=body.meta())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/preguntas")
def get_questions():
    return list_questions()


@app.post("/api/preguntas")
def post_question(body: QuestionIn):
    try:
        return add_question(
            body.prompt,
            body.answer,
            body.skill,
            body.materia,
            body.kind,
            body.criterion,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/preguntas/vista")
def post_preview(body: QuestionIn):
    return {"variants": preview_variants(body.prompt, body.answer, body.skill)}


@app.post("/api/materias")
def post_materia(body: MateriaIn):
    try:
        return add_materia(body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/preguntas/{question_id}")
def remove_question(question_id: str):
    return delete_question(question_id)


@app.post("/api/diagnostico")
def post_diagnostic(body: DiagnosticIn):
    names = [name.strip() for name in body.names if name.strip()]
    if not names or len(names) > 40:
        raise HTTPException(400, "Escribe entre 1 y 40 nombres.")
    try:
        return create_diagnostic(
            body.group.strip(), names, random.Random(), materias=body.materias, meta=body.meta()
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/calificar")
async def post_grade(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "La imagen llegó vacía.")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Ese archivo no es una imagen.")
    try:
        result = grade_photo(image)
    except GradeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return with_context(result)


@app.post("/api/interpretar")
def post_interpretation(body: InterpretIn):
    try:
        result = save_interpretation(body.sheet_id, body.marks)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return with_context(result)


@app.get("/api/clase")
def get_class(group: str, form_id: str = ""):
    return class_report(group.strip(), form_id or None)


@app.get("/api/grupos")
def get_groups(group: str = ""):
    return groups_and_students(group.strip() or None)


def _bimestre(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(400, "El bimestre debe ser un número del 1 al 4.") from exc


@app.get("/api/notas")
def get_grid(group: str, bimestre: str = ""):
    return grid(load(), group.strip(), _bimestre(bimestre))


@app.get("/api/notas-anuales")
def get_yearly(group: str):
    return yearly(load(), group.strip())


@app.get("/api/notas.csv")
def get_csv(group: str, vista: str = "cuadro", bimestre: str = "", modo: str = "real"):
    group = group.strip()
    modo = "relativa" if modo == "relativa" else "real"
    if vista == "anual":
        body = csv_yearly(yearly(load(), group), modo)
        name = f"notas-{group}-anual.csv"
    else:
        number = _bimestre(bimestre)
        body = csv_grid(grid(load(), group, number), modo)
        name = f"notas-{group}-{'bimestre-' + str(number) if number else 'todo'}.csv"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return Response(
        body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@app.delete("/api/examenes/{form_id}")
def remove_exam(form_id: str):
    try:
        return delete_exam(form_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/refuerzo")
def post_reinforcement(body: ReinforceIn):
    try:
        return create_reinforcement(body.group.strip(), body.student_name.strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/simular")
def post_simulate(body: SimulateIn):
    report = simulate_class(body.group.strip())
    return {
        "patterns": report["patterns"],
        "graded": [
            {
                "student_name": item["student_name"],
                "score": item["score"],
                "total": item["total"],
            }
            for item in report["graded"]
        ],
    }
