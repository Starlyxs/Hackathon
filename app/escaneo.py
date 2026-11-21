"""Califica hojas escaneadas: un PDF de CamScanner, de Google Drive o de una copiadora,
o varias fotos planas. Cada página trae su QR, así que el programa sabe de quién es
y qué hoja del examen es, aunque las páginas vengan mezcladas o falte alguna."""

import threading
import time
import uuid

import cv2
import numpy as np

from app import service
from app.grade import GradeError, is_blank_page, read_scan
from app.notas import form_meta, latest_by_sheet
from app.store import SHEETS, load

SCANS = SHEETS / "escaneos"
MAX_PAGES = 400
LONG_SIDE = 2400  # píxeles del lado largo al abrir una página de PDF (≈ 200 dpi en carta)
KEEP_JOBS = 8

_jobs = {}
_jobs_lock = threading.Lock()


def is_pdf(raw):
    return b"%PDF-" in raw[:1024]


def _open_pdf(raw):
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(raw)
    except Exception as exc:  # el archivo está dañado o tiene contraseña
        raise GradeError("No pude abrir ese PDF. Puede estar dañado o tener contraseña.") from exc


def pages_in(raw):
    if not is_pdf(raw):
        return 1
    pdf = _open_pdf(raw)
    try:
        return len(pdf)
    finally:
        pdf.close()


def iter_pages(raw):
    """Entrega cada página como imagen BGR."""
    if not is_pdf(raw):
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise GradeError("Ese archivo no es un PDF ni una imagen.")
        yield 1, image
        return
    pdf = _open_pdf(raw)
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                width, height = page.get_size()
                scale = LONG_SIDE / max(width, height, 1)
                bitmap = page.render(scale=scale)
                array = np.ascontiguousarray(bitmap.to_numpy())
            finally:
                page.close()
            if array.ndim == 3 and array.shape[2] == 4:
                array = cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
            yield index + 1, array
    finally:
        pdf.close()


def _save_scan(sheet_id, aligned):
    SCANS.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".jpg", aligned, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if ok:
        (SCANS / f"{sheet_id}.jpg").write_bytes(encoded.tobytes())


def scan_url(sheet_id):
    path = SCANS / f"{sheet_id}.jpg"
    if not path.exists():
        return ""
    return f"/archivos/escaneos/{sheet_id}.jpg?t={int(path.stat().st_mtime)}"


def _hoja_label(sheet):
    return f"hoja {sheet['hoja']}" if sheet.get("hoja") else "la hoja"


def handle_page(label, bgr, form_id, replace):
    """Lee y califica una página. Nunca lanza: devuelve qué pasó con ella."""
    entry = {"pagina": label, "estado": "error", "mensaje": ""}
    if is_blank_page(bgr):
        entry.update(estado="blanca", mensaje="Página en blanco; se omitió.")
        return entry
    try:
        aligned, sheet_id = read_scan(bgr)
    except GradeError as exc:
        entry["mensaje"] = str(exc)
        return entry
    db = load()
    sheet = db["sheets"].get(sheet_id)
    if sheet is None:
        entry["mensaje"] = "Ese QR no es de esta laptop. La hoja se generó en otra computadora."
        return entry
    entry.update(
        sheet_id=sheet_id,
        alumno=sheet["student_name"],
        hoja=sheet.get("hoja") or "",
        form_id=sheet.get("form_id") or "",
    )
    try:
        service.check_sheet(db, sheet, form_id or None)
    except GradeError as exc:
        entry["mensaje"] = str(exc)
        return entry
    if not replace and sheet_id in latest_by_sheet(db):
        entry.update(estado="repetida", mensaje="Ya tenía nota; no se cambió.")
        return entry
    try:
        result = service.grade_aligned(aligned, sheet_id, form_id or None)
    except GradeError as exc:
        entry["mensaje"] = str(exc)
        return entry
    _save_scan(sheet_id, aligned)
    if result.get("needs_review"):
        result["imagen"] = scan_url(sheet_id)
        entry.update(estado="revisar", mensaje="Falta marcar lo escrito.", revisar=result)
    else:
        entry.update(
            estado="calificada",
            puntos=f"{round(float(result['score']), 2):g} de {round(float(result['total']), 2):g}",
            mensaje="",
        )
    return entry


def completeness(db, form_id):
    """Quién entregó todas sus hojas, a quién le falta alguna y quién no entregó nada."""
    form = db["forms"].get(form_id)
    if form is None:
        return None
    meta = form_meta(form)
    latest = latest_by_sheet(db)
    pending = db.get("pending") or {}
    people = {}
    for sheet in db["sheets"].values():
        if sheet.get("form_id") == form_id:
            people.setdefault(sheet["student_name"], []).append(sheet)
    complete = 0
    incomplete = []
    absent = []
    review = []
    for name in sorted(people, key=str.lower):
        sheets = sorted(people[name], key=lambda item: item.get("pagina") or 1)
        waiting = [item for item in sheets if item["id"] in pending]
        done = [item for item in sheets if item["id"] in latest and item["id"] not in pending]
        missing = [item for item in sheets if item not in waiting and item not in done]
        for item in waiting:
            review.append({"alumno": name, "hoja": item.get("hoja") or "", "sheet_id": item["id"]})
        if not missing and not waiting:
            complete += 1
        elif not done and not waiting:
            absent.append(name)
        elif missing:
            incomplete.append(
                {
                    "alumno": name,
                    "faltan": [_hoja_label(item) for item in missing],
                    "tiene": [_hoja_label(item) for item in done + waiting],
                }
            )
    return {
        "form_id": form_id,
        "titulo": meta["titulo_completo"],
        "alumnos": len(people),
        "completos": complete,
        "incompletos": incomplete,
        "sin_entregar": absent,
        "por_revisar": review,
    }


def pending_reviews(form_id=""):
    """Hojas con preguntas escritas que ya se leyeron y esperan que la maestra marque lo escrito."""
    db = load()
    found = []
    for sheet_id, pending in (db.get("pending") or {}).items():
        sheet = db["sheets"].get(sheet_id)
        if sheet is None or (form_id and sheet.get("form_id") != form_id):
            continue
        form = db["forms"].get(sheet.get("form_id") or "")
        if form is None or form.get("papelera"):
            continue
        payload = service.review_payload(sheet, pending)
        payload["imagen"] = scan_url(sheet_id)
        found.append(payload)
    found.sort(key=lambda item: (item["student_name"].lower(), item["hoja"]))
    return found


def _summary(entries):
    count = lambda state: sum(1 for entry in entries if entry["estado"] == state)
    return {
        "calificadas": count("calificada"),
        "revisar": count("revisar"),
        "repetidas": count("repetida"),
        "blancas": count("blanca"),
        "errores": count("error"),
    }


def _run(job_id, files, form_id, replace):
    job = _jobs[job_id]
    try:
        for name, raw in files:
            try:
                for number, bgr in iter_pages(raw):
                    label = f"{name} · página {number}" if len(files) > 1 or is_pdf(raw) else name
                    job["paginas"].append(handle_page(label, bgr, form_id, replace))
                    job["hechas"] += 1
            except GradeError as exc:
                job["paginas"].append({"pagina": name, "estado": "error", "mensaje": str(exc)})
                job["hechas"] += 1
        db = load()
        touched = []
        for entry in job["paginas"]:
            wanted = entry.get("form_id")
            if wanted and wanted not in touched and entry["estado"] in ("calificada", "revisar", "repetida"):
                touched.append(wanted)
        if form_id and form_id not in touched:
            touched.append(form_id)
        job["resumen"] = _summary(job["paginas"])
        job["examenes"] = [row for row in (completeness(db, wanted) for wanted in touched) if row]
        job["estado"] = "listo"
    except Exception as exc:  # un fallo inesperado no debe dejar la barra girando para siempre
        job["estado"] = "error"
        job["mensaje"] = f"Algo salió mal al leer el archivo: {exc}"
    finally:
        job["terminado"] = time.time()


def start(files, form_id="", replace=False):
    """files: lista de (nombre, bytes). Devuelve el id del trabajo para ir preguntando el avance."""
    total = 0
    problems = []
    for name, raw in files:
        try:
            total += pages_in(raw)
        except GradeError as exc:
            problems.append({"pagina": name, "estado": "error", "mensaje": str(exc)})
            total += 1
    if total > MAX_PAGES:
        raise ValueError(f"Son demasiadas páginas ({total}). Sube hasta {MAX_PAGES} a la vez.")
    readable = []
    bad = {entry["pagina"] for entry in problems}
    for name, raw in files:
        if name not in bad:
            readable.append((name, raw))
    job_id = uuid.uuid4().hex[:10]
    job = {
        "id": job_id,
        "estado": "corriendo",
        "total": total,
        "hechas": len(problems),
        "paginas": list(problems),
        "resumen": None,
        "examenes": [],
        "mensaje": "",
        "creado": time.time(),
    }
    with _jobs_lock:
        _jobs[job_id] = job
        for old in sorted(_jobs.values(), key=lambda item: item["creado"])[:-KEEP_JOBS]:
            _jobs.pop(old["id"], None)
    threading.Thread(target=_run, args=(job_id, readable, form_id, replace), daemon=True).start()
    return job_id


def progress(job_id):
    job = _jobs.get(job_id)
    if job is None:
        return None
    return {key: value for key, value in job.items() if key != "creado"}
