"""Exámenes por series: reparte los puntos, acomoda las preguntas en hojas y las dibuja.

Una serie es un bloque del examen («Serie I», «Serie II»…) con su instrucción, una imagen
opcional, los puntos que vale y sus preguntas. Las preguntas de todas las series se acomodan
una tras otra y solo se agrega una hoja cuando la anterior se llena, así no sobran hojas vacías.
"""

import io
import re
import uuid
from functools import lru_cache

from PIL import Image, ImageDraw, ImageOps

from app import render as base
from app.layout import BUBBLE_R, H, MARKER, OPTIONS_X, QR_SIZE, QR_XY, W, marker_boxes
from app.store import SHEETS, ensure_dirs

TIPOS = {"opciones": "Opción múltiple", "escrita": "Respuesta escrita"}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
MAX_SERIES = 8
MAX_QUESTIONS = 30

LEFT = 72
RIGHT = W - 72
CONTENT_TOP = 452
CONTENT_BOTTOM = H - MARKER - 88
IMAGE_MAX_H = 320
WRITE_BOX_H = 110
TEXT_X = 118

_IMAGE_ID = re.compile(r"^[0-9a-f]{10}$")


def points_text(value):
    return f"{round(float(value), 2):g}"


def series_name(index):
    return f"Serie {ROMAN[index] if index < len(ROMAN) else index + 1}"


# ---------- imágenes ----------
def save_image(raw):
    """Guarda la imagen de una serie, ya recortada a un tamaño razonable."""
    if not raw:
        raise ValueError("La imagen llegó vacía.")
    if len(raw) > 12_000_000:
        raise ValueError("La imagen pesa demasiado. Usa una de menos de 12 MB.")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001 - cualquier archivo que no sea imagen
        raise ValueError("Ese archivo no es una imagen.") from exc
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.split()[3])
        image = flat
    else:
        image = image.convert("RGB")
    image.thumbnail((1400, 1000))
    ensure_dirs()
    image_id = uuid.uuid4().hex[:10]
    image.save(SHEETS / f"img-{image_id}.jpg", "JPEG", quality=88)
    return {"id": image_id, "url": f"/archivos/img-{image_id}.jpg"}


def image_file(image_id):
    if not image_id or not _IMAGE_ID.match(image_id):
        return None
    path = SHEETS / f"img-{image_id}.jpg"
    return path if path.exists() else None


# ---------- validar y repartir puntos ----------
def prepare(bank, series, nota_total, chosen=None):
    """Revisa las series y calcula cuánto vale cada pregunta. Lanza ValueError con un mensaje claro."""
    byid = {row["id"]: row for row in bank}
    if not series:
        raise ValueError("Agrega al menos una serie con sus preguntas.")
    if len(series) > MAX_SERIES:
        raise ValueError(f"Un examen admite hasta {MAX_SERIES} series.")
    seen = set()
    prepared = []
    total_points = 0.0
    count = 0
    for index, item in enumerate(series):
        tipo = item.get("tipo")
        if tipo not in TIPOS:
            raise ValueError("El tipo de serie no es válido.")
        name = " ".join((item.get("nombre") or "").split())[:30] or series_name(index)
        ids = [value for value in (item.get("question_ids") or []) if value]
        if not ids:
            raise ValueError(f"{name} no tiene preguntas. Agrégale al menos una o quítala.")
        rows = []
        for question_id in ids:
            row = byid.get(question_id)
            if row is None:
                raise ValueError("Una de las preguntas elegidas ya no existe.")
            if question_id in seen:
                raise ValueError(f"La pregunta «{row['prompt'][:40]}» está en dos series.")
            seen.add(question_id)
            closed = row.get("kind", "cerrada") != "abierta"
            if (tipo == "opciones") != closed:
                raise ValueError(f"{name} es de {TIPOS[tipo].lower()}: quita las preguntas del otro tipo.")
            if chosen and row.get("materia") not in chosen:
                raise ValueError(f"Este examen es de {', '.join(chosen)}; quita las preguntas de otra materia.")
            rows.append(row)
        try:
            points = float(item.get("puntos") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Los puntos de {name} no son un número.") from exc
        if not points > 0:
            raise ValueError(f"Pon cuántos puntos vale {name}.")
        image = (item.get("imagen") or "").strip()
        if image and image_file(image) is None:
            raise ValueError(f"La imagen de {name} ya no está. Súbela otra vez.")
        count += len(rows)
        total_points += points
        prepared.append(
            {
                "nombre": name,
                "tipo": tipo,
                "instruccion": " ".join((item.get("instruccion") or "").split())[:240],
                "imagen": image,
                "puntos": points,
                "por_pregunta": points / len(rows),
                "rows": rows,
            }
        )
    if count > MAX_QUESTIONS:
        raise ValueError(f"Un examen admite hasta {MAX_QUESTIONS} preguntas.")
    if total_points > float(nota_total) + 1e-9:
        raise ValueError(
            f"Las series suman {points_text(total_points)} puntos y el examen vale {points_text(nota_total)}. "
            "Baja los puntos de alguna serie."
        )
    return prepared


# ---------- acomodar en hojas ----------
@lru_cache(maxsize=1)
def _fonts():
    return {
        "title": base.load_font(30, bold=True),
        "number": base.load_font(26, bold=True),
        "prompt": base.load_font(24),
        "sub": base.load_font(21),
        "instruction": base.load_font(20),
        "option": base.load_font(18),
        "small": base.load_font(16),
    }


def _scratch():
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


def _fit(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def _image_box(image_id):
    path = image_file(image_id)
    if path is None:
        return None
    with Image.open(path) as image:
        width, height = image.size
    max_w = RIGHT - LEFT
    scale = min(max_w / width, IMAGE_MAX_H / height, 1.0)
    out_w, out_h = max(1, int(width * scale)), max(1, int(height * scale))
    return {"w": out_w, "h": out_h, "x": LEFT + (max_w - out_w) // 2}


def _header_items(block, y):
    """Título de la serie, instrucción e imagen. Devuelve (items, alto)."""
    fonts = _fonts()
    draw = _scratch()
    lines = base.wrap_text(draw, block["instruccion"], fonts["instruction"], RIGHT - LEFT)[:3] if block["instruccion"] else []
    count = len(block["preguntas"])
    detail = f"{TIPOS[block['tipo']]}  ·  vale {points_text(block['puntos'])} puntos"
    if count > 1:
        detail += f"  ({points_text(block['por_pregunta'])} cada una)"
    items = [{"t": "serie", "y": y, "titulo": block["nombre"], "detalle": detail, "lineas": lines}]
    height = 70 + 26 * len(lines)
    box = _image_box(block["imagen"]) if block["imagen"] else None
    if box:
        items.append({"t": "img", "y": y + height, "imagen": block["imagen"], **box})
        height += box["h"] + 14
    return items, height + 12


def _question_height(question):
    fonts = _fonts()
    draw = _scratch()
    if question.get("format") == "abierta":
        lines = base.wrap_text(draw, question["prompt"], fonts["prompt"], RIGHT - TEXT_X - 90)[:4]
        return 28 * len(lines) + 12 + WRITE_BOX_H + 30, lines
    lines = base.wrap_text(draw, question["prompt"], fonts["prompt"], RIGHT - TEXT_X - 90)[:3]
    return 28 * len(lines) + 98, lines


def paginate(blocks):
    """Acomoda todas las series en las hojas que hagan falta. Devuelve una lista de páginas."""
    pages = []

    def start():
        pages.append({"layout": [], "questions": []})
        return CONTENT_TOP

    y = start()
    for block in blocks:
        header, header_h = _header_items(block, 0)
        first_h, _ = _question_height(block["preguntas"][0])
        if pages[-1]["layout"] and y + header_h + first_h > CONTENT_BOTTOM:
            y = start()
        for item in header:
            item["y"] += y
            pages[-1]["layout"].append(item)
        y += header_h
        for question in block["preguntas"]:
            height, lines = _question_height(question)
            if y + height > CONTENT_BOTTOM and pages[-1]["questions"]:
                y = start()
                pages[-1]["layout"].append({"t": "cont", "y": y, "titulo": f"{block['nombre']} (continúa)"})
                y += 44
            page = pages[-1]
            index = len(page["questions"])
            page["questions"].append(question)
            if question.get("format") == "abierta":
                box_top = y + 28 * len(lines) + 12
                page["layout"].append(
                    {
                        "t": "q_open",
                        "qi": index,
                        "y": y,
                        "numero": question["numero"],
                        "lineas": lines,
                        "caja": [LEFT, box_top, RIGHT, box_top + WRITE_BOX_H],
                        "puntos": question["puntos"],
                    }
                )
            else:
                by = y + 28 * len(lines) + 46
                page["layout"].append(
                    {
                        "t": "q_closed",
                        "qi": index,
                        "y": y,
                        "numero": question["numero"],
                        "lineas": lines,
                        "opciones": list(question["options"]),
                        "bubbles": [[x, by] for x in OPTIONS_X],
                        "puntos": question["puntos"],
                    }
                )
            y += height
    return pages


def bubble_slots(sheet):
    """Posición de las burbujas de cada pregunta de opciones, en el orden de la hoja."""
    return [item["bubbles"] for item in sheet["layout"] if item["t"] == "q_closed"]


# ---------- dibujar ----------
def render_page(sheet):
    fonts = _fonts()
    image = Image.new("RGB", (W, H), base.PAPER)
    draw = ImageDraw.Draw(image)
    for x, y, w, h in marker_boxes().values():
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill="black")

    formats = {question.get("format") for question in sheet["questions"]}
    draw.text((126, 58), base._heading(sheet, "Examen"), fill=base.ACCENT, font=base.load_font(40, bold=True))
    draw.text((126, 112), sheet.get("materia_label") or "", fill=base.INK, font=base.load_font(22))
    draw.text((LEFT, 154), base._student_line(sheet), fill=base.INK, font=base.load_font(22))
    draw.text((LEFT, 188), base._group_line(sheet), fill=base.INK, font=base.load_font(22))
    hints = []
    if "cerrada" in formats:
        hints.append("Rellena una burbuja por pregunta.")
    if "abierta" in formats:
        hints.append("Responde con tus palabras.")
    draw.text((LEFT, 232), "  ".join(hints), fill=base.INK, font=fonts["small"])
    qx, qy = QR_XY
    image.paste(base._qr_image(f"EDU1:{sheet['id']}"), (qx, qy))
    draw.text((qx, qy + QR_SIZE + 8), sheet["id"], fill=base.INK, font=fonts["small"])

    for item in sheet["layout"]:
        y = item["y"]
        kind = item["t"]
        if kind == "serie":
            draw.line((LEFT, y - 6, RIGHT, y - 6), fill=base.ACCENT, width=2)
            draw.text((LEFT, y), item["titulo"], fill=base.ACCENT, font=fonts["title"])
            draw.text((LEFT, y + 38), item["detalle"], fill=base.INK, font=fonts["sub"])
            for index, line in enumerate(item["lineas"]):
                draw.text((LEFT, y + 68 + index * 26), line, fill=base.INK, font=fonts["instruction"])
        elif kind == "cont":
            draw.line((LEFT, y - 6, RIGHT, y - 6), fill=base.ACCENT, width=2)
            draw.text((LEFT, y), item["titulo"], fill=base.ACCENT, font=fonts["sub"])
        elif kind == "img":
            path = image_file(item["imagen"])
            if path is not None:
                with Image.open(path) as picture:
                    picture = picture.convert("RGB").resize((item["w"], item["h"]), Image.Resampling.LANCZOS)
                image.paste(picture, (item["x"], y))
                draw.rectangle((item["x"], y, item["x"] + item["w"], y + item["h"]), outline=(150, 146, 136), width=2)
        elif kind in ("q_closed", "q_open"):
            draw.text((LEFT, y), f"{item['numero']}.", fill=base.ACCENT, font=fonts["number"])
            tag = f"{points_text(item['puntos'])} pts"
            draw.text((RIGHT - draw.textlength(tag, font=fonts["small"]), y + 4), tag, fill=(110, 112, 104), font=fonts["small"])
            for index, line in enumerate(item["lineas"]):
                draw.text((TEXT_X, y + index * 28), line, fill=base.INK, font=fonts["prompt"])
            if kind == "q_open":
                x1, y1, x2, y2 = item["caja"]
                draw.rectangle((x1, y1, x2, y2), outline=base.INK, width=2)
                for line_y in (y1 + 36, y1 + 72):
                    draw.line((x1 + 16, line_y, x2 - 16, line_y), fill=(180, 176, 166), width=1)
            else:
                for letter, option, (bx, by) in zip("ABCD", item["opciones"], item["bubbles"]):
                    draw.ellipse((bx - BUBBLE_R, by - BUBBLE_R, bx + BUBBLE_R, by + BUBBLE_R), outline=base.INK, width=3)
                    draw.text((bx - 6, by - BUBBLE_R - 20), letter, fill=base.INK, font=fonts["small"])
                    draw.text((bx + 26, by - 10), _fit(draw, str(option), fonts["option"], 200), fill=base.INK, font=fonts["option"])

    draw.text(
        (LEFT, H - MARKER - 78),
        "Los cuadros negros de las esquinas alinean la hoja. No los tapes con la mano.",
        fill=base.INK,
        font=fonts["small"],
    )
    return image
