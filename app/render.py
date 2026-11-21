"""Dibuja la hoja en la misma retícula que después lee la cámara."""

from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

from app.bank import SKILLS
from app.layout import BUBBLE_R, H, MARKER, QR_SIZE, QR_XY, W, marker_boxes, question_slots

INK = (24, 32, 28)
PAPER = (255, 252, 245)
ACCENT = (22, 92, 68)


def load_font(size, bold=False):
    names = ["arialbd.ttf", "segoeuib.ttf"] if bold else ["arial.ttf", "segoeui.ttf"]
    windows = Path(r"C:\Windows\Fonts")
    linux = Path("/usr/share/fonts/truetype/dejavu")
    linux_names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for folder, candidates in ((windows, names), (linux, linux_names)):
        for name in candidates:
            path = folder / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    lines = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _qr_image(payload):
    qr = qrcode.QRCode(border=2, box_size=8, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((QR_SIZE, QR_SIZE), Image.Resampling.NEAREST)


def _heading(sheet, fallback):
    if sheet.get("kind") == "refuerzo":
        return "Hoja de refuerzo"
    title = sheet.get("titulo")
    if not title:
        return fallback
    if sheet.get("bimestre"):
        title = f"{title} · Bimestre {sheet['bimestre']}"
    return title if len(title) <= 28 else title[:27] + "…"


def _student_line(sheet):
    line = f"Alumno: {sheet['student_name']}"
    if sheet.get("hoja"):
        line += f"   ·   Hoja {sheet['hoja']}"
    return line


def _group_line(sheet):
    line = f"Grupo: {sheet['group']}"
    points = sheet.get("nota_total")
    if points and sheet.get("kind") != "refuerzo":
        line += f"   ·   Vale {points:g} puntos"
    return line


def render_sheet(sheet):
    if sheet.get("format") == "abierta":
        return _render_open(sheet)
    image = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    title_font = load_font(40, bold=True)
    meta_font = load_font(22)
    prompt_font = load_font(24)
    option_font = load_font(18)
    small_font = load_font(16)

    for x, y, w, h in marker_boxes().values():
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill="black")

    draw.text((72, 58), _heading(sheet, "Diagnóstico"), fill=ACCENT, font=title_font)
    draw.text((72, 112), sheet.get("materia_label") or "Matemática y lectura  ·  4° a 6°", fill=INK, font=meta_font)
    draw.text((72, 154), _student_line(sheet), fill=INK, font=meta_font)
    draw.text((72, 188), _group_line(sheet), fill=INK, font=meta_font)
    draw.text(
        (72, 232),
        "Rellena por completo una burbuja por pregunta. No marques fuera del círculo.",
        fill=INK,
        font=small_font,
    )

    qx, qy = QR_XY
    image.paste(_qr_image(f"EDU1:{sheet['id']}"), (qx, qy))
    draw.text((qx, qy + QR_SIZE + 8), sheet["id"], fill=INK, font=small_font)

    slots = question_slots(len(sheet["questions"]))
    for number, (question, slot) in enumerate(zip(sheet["questions"], slots), start=1):
        px, py = slot["prompt"]
        skill = SKILLS.get(question["skill"], question["skill"])
        draw.text((px, py - 22), f"{number}   {skill}", fill=ACCENT, font=small_font)
        lines = wrap_text(draw, question["prompt"], prompt_font, W - 140)
        for i, line in enumerate(lines[:2]):
            draw.text((px, py + i * 28), line, fill=INK, font=prompt_font)
        for letter, option, (bx, by) in zip("ABCD", question["options"], slot["bubbles"]):
            draw.ellipse(
                (bx - BUBBLE_R, by - BUBBLE_R, bx + BUBBLE_R, by + BUBBLE_R),
                outline=INK,
                width=3,
            )
            draw.text((bx - 6, by - BUBBLE_R - 20), letter, fill=INK, font=small_font)
            draw.text((bx + 26, by - 10), option, fill=INK, font=option_font)

    draw.text(
        (72, H - MARKER - 78),
        "Los cuadros negros de las esquinas alinean la hoja. No los tapes con la mano.",
        fill=INK,
        font=small_font,
    )
    return image


def _render_open(sheet):
    image = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    title_font = load_font(40, bold=True)
    meta_font = load_font(22)
    prompt_font = load_font(24)
    small_font = load_font(16)
    for x, y, w, h in marker_boxes().values():
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill="black")
    draw.text((72, 58), _heading(sheet, "Interpretación"), fill=ACCENT, font=title_font)
    subject = sheet.get("materia_label") or "Varias materias"
    draw.text((72, 112), f"Interpretación · {subject}" if sheet.get("titulo") else subject, fill=INK, font=meta_font)
    draw.text((72, 154), _student_line(sheet), fill=INK, font=meta_font)
    draw.text((72, 188), _group_line(sheet), fill=INK, font=meta_font)
    draw.text(
        (72, 232),
        "Responde con tus palabras. Se lee la idea, no la ortografía.",
        fill=INK,
        font=small_font,
    )
    qx, qy = QR_XY
    image.paste(_qr_image(f"EDU1:{sheet['id']}"), (qx, qy))
    draw.text((qx, qy + QR_SIZE + 8), sheet["id"], fill=INK, font=small_font)
    top = 470
    height = 250
    for number, question in enumerate(sheet["questions"], start=1):
        y = top + (number - 1) * height
        materia = question.get("materia") or "Interpretación"
        draw.text((72, y), f"{number}   {materia}", fill=ACCENT, font=small_font)
        lines = wrap_text(draw, question["prompt"], prompt_font, W - 150)
        for index, line in enumerate(lines[:3]):
            draw.text((72, y + 24 + index * 28), line, fill=INK, font=prompt_font)
        box_top = y + 120
        draw.rectangle((72, box_top, W - 72, box_top + 100), outline=INK, width=2)
        for line_y in (box_top + 32, box_top + 64):
            draw.line((88, line_y, W - 88, line_y), fill=(180, 176, 166), width=1)
    draw.text(
        (72, H - MARKER - 78),
        "Los cuadros negros de las esquinas alinean la hoja. No los tapes con la mano.",
        fill=INK,
        font=small_font,
    )
    return image


def save_pdf(image, path):
    path = Path(path)
    image.save(path, "PDF", resolution=150.0)
    return path
