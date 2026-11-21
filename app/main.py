"""Servidor local. Se abre en el navegador de la misma laptop."""

import random
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.demo import simulate_class
from app.grade import GradeError, quick_sheet_id
from app.notas import csv_grid, csv_yearly, grid, yearly
from app.service import (
    add_materia,
    add_question,
    class_report,
    create_diagnostic,
    create_reinforcement,
    create_series_exam,
    delete_group,
    delete_question,
    exam_summary,
    grade_photo,
    groups_and_students,
    list_exams,
    list_my_groups,
    list_questions,
    overview,
    preview_diagnostic,
    preview_series_exam,
    purge_exam,
    restore_exam,
    save_group,
    save_interpretation,
    set_exam_off,
    sheet_status,
    trash_exam,
)
from app.series import save_image as save_series_image
from app.store import SHEETS, ensure_dirs, load
from app.variants import preview_variants

ensure_dirs()
STATIC = Path(__file__).resolve().parent / "static"
STATIC.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Hojas en papel")
app.mount("/archivos", StaticFiles(directory=str(SHEETS)), name="archivos")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

PASOS = (
    ("inicio", "/", "Inicio"),
    ("grupos", "/grupos", "1. Grupos"),
    ("examenes", "/examenes", "2. Exámenes"),
    ("calificar", "/calificar", "3. Calificar"),
    ("notas", "/notas", "4. Notas del año"),
    ("analisis", "/analisis", "Análisis"),
)


def html_page(name, active=""):
    path = Path(__file__).parent / "templates" / name
    links = ""
    for key, href, label in PASOS:
        mark = ' class="active"' if key == active else ""
        links += f'<a href="{href}"{mark}>{label}</a>'
    html = path.read_text(encoding="utf-8").replace("<!--NAV-->", f"<nav>{links}</nav>")
    return HTMLResponse(html)


class SerieIn(BaseModel):
    nombre: str = Field(default="", max_length=30)
    tipo: str = "opciones"
    instruccion: str = Field(default="", max_length=240)
    imagen: str = Field(default="", max_length=20)
    puntos: float = Field(default=0, ge=0, le=1000)
    question_ids: list[str] = []

    def data(self):
        return {
            "nombre": self.nombre,
            "tipo": self.tipo,
            "instruccion": self.instruccion,
            "imagen": self.imagen,
            "puntos": self.puntos,
            "question_ids": self.question_ids,
        }


class DiagnosticIn(BaseModel):
    group: str = Field(min_length=1, max_length=40)
    names: list[str] = []
    materias: list[str] = []
    question_ids: list[str] = []
    series: list[SerieIn] = []
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


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    students: list[str] = []


class OffIn(BaseModel):
    off: bool = True


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
    return html_page("inicio.html", "inicio")


@app.get("/calificar")
def grade_page():
    return html_page("calificar.html", "calificar")


@app.get("/grupos")
def groups_page():
    return html_page("grupos.html", "grupos")


@app.get("/analisis")
def analysis_page():
    return html_page("analisis.html", "analisis")


@app.get("/api/estado")
def get_overview():
    return overview()


@app.get("/api/mis-grupos")
def get_my_groups():
    return list_my_groups()


@app.post("/api/mis-grupos")
def post_group(body: GroupIn):
    try:
        return save_group(body.name, body.students)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/mis-grupos/{name}")
def remove_group(name: str):
    try:
        return delete_group(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/preguntas")
def questions_page():
    # Las preguntas ahora se escriben dentro de Exámenes; se mantiene el enlace viejo.
    return RedirectResponse("/examenes")


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
    try:
        if body.series:
            return preview_series_exam(
                body.group.strip(),
                names,
                random.Random(),
                [item.data() for item in body.series],
                materias=body.materias,
                meta=body.meta(),
            )
        return preview_diagnostic(
            body.group.strip(),
            names,
            random.Random(),
            materias=body.materias,
            meta=body.meta(),
            question_ids=body.question_ids,
        )
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
    try:
        if body.series:
            return create_series_exam(
                body.group.strip(),
                names,
                random.Random(),
                [item.data() for item in body.series],
                materias=body.materias,
                meta=body.meta(),
            )
        return create_diagnostic(
            body.group.strip(),
            names,
            random.Random(),
            materias=body.materias,
            meta=body.meta(),
            question_ids=body.question_ids,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/imagenes")
async def post_series_image(file: UploadFile = File(...)):
    """Imagen que acompaña a una serie (un mapa, un dibujo, una lectura escaneada)."""
    try:
        return save_series_image(await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def read_image(file):
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "La imagen llegó vacía.")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Ese archivo no es una imagen.")
    return image


@app.post("/api/escanear")
async def post_scan(file: UploadFile = File(...), form_id: str = Form("")):
    """Cuadro de la cámara en vivo: ¿hay una hoja a la vista y de quién es?"""
    image = await read_image(file)
    sheet_id = quick_sheet_id(image)
    if sheet_id is None:
        return {"estado": "buscando"}
    return {"estado": "qr", **sheet_status(sheet_id, form_id or None)}


@app.post("/api/calificar")
async def post_grade(file: UploadFile = File(...), form_id: str = Form("")):
    image = await read_image(file)
    try:
        result = grade_photo(image, form_id or None)
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
def get_grid(group: str, bimestre: str = "", materia: str = ""):
    return grid(load(), group.strip(), _bimestre(bimestre), materia.strip() or None)


@app.get("/api/notas-anuales")
def get_yearly(group: str, materia: str = ""):
    return yearly(load(), group.strip(), materia.strip() or None)


@app.get("/api/notas.csv")
def get_csv(group: str, vista: str = "cuadro", bimestre: str = "", modo: str = "real", materia: str = ""):
    group = group.strip()
    materia = materia.strip() or None
    modo = "relativa" if modo == "relativa" else "real"
    label = f"{group}-{materia}" if materia else group
    if vista == "anual":
        body = csv_yearly(yearly(load(), group, materia), modo)
        name = f"notas-{label}-anual.csv"
    else:
        number = _bimestre(bimestre)
        body = csv_grid(grid(load(), group, number, materia), modo)
        name = f"notas-{label}-{'bimestre-' + str(number) if number else 'todo'}.csv"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return Response(
        body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


def _exam_action(action, *args):
    try:
        return action(*args)
    except ValueError as exc:
        raise HTTPException(409 if str(exc).startswith("Ya existe") else 404, str(exc)) from exc


@app.delete("/api/examenes/{form_id}")
def remove_exam(form_id: str):
    return _exam_action(trash_exam, form_id)


@app.post("/api/examenes/{form_id}/restaurar")
def undo_remove_exam(form_id: str):
    return _exam_action(restore_exam, form_id)


@app.delete("/api/examenes/{form_id}/definitivo")
def purge_exam_route(form_id: str):
    return _exam_action(purge_exam, form_id)


@app.post("/api/examenes/{form_id}/apagar")
def switch_exam(form_id: str, body: OffIn):
    return _exam_action(set_exam_off, form_id, body.off)


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
