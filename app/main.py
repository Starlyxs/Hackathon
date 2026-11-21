"""Servidor local. Se abre en el navegador de la misma laptop."""

import random
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.demo import simulate_class
from app.grade import GradeError
from app.service import (
    add_materia,
    add_question,
    class_report,
    create_diagnostic,
    create_reinforcement,
    delete_question,
    grade_photo,
    list_questions,
    save_interpretation,
)
from app.store import SHEETS, ensure_dirs
from app.variants import preview_variants

ensure_dirs()
app = FastAPI(title="Hojas en papel")
app.mount("/archivos", StaticFiles(directory=str(SHEETS)), name="archivos")

def html_page(name):
    path = Path(__file__).parent / "templates" / name
    return HTMLResponse(path.read_text(encoding="utf-8"))


class DiagnosticIn(BaseModel):
    group: str = Field(min_length=1, max_length=40)
    names: list[str]
    materias: list[str] = []


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


@app.get("/")
def home():
    return html_page("index.html")


@app.get("/preguntas")
def questions_page():
    return html_page("preguntas.html")


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
        return create_diagnostic(body.group.strip(), names, random.Random(), materias=body.materias)
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
    report = class_report(result["group"])
    result["patterns"] = report["patterns"]
    return result


@app.post("/api/interpretar")
def post_interpretation(body: InterpretIn):
    try:
        result = save_interpretation(body.sheet_id, body.marks)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    report = class_report(result["group"])
    result["patterns"] = report["patterns"]
    return result


@app.get("/api/clase")
def get_class(group: str):
    return class_report(group.strip())


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
