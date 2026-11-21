"""Arma el video tutorial (app/static/tutorial.webm) a partir de capturas de pantalla de la app.

Uso:  python herramientas/crear_tutorial.py CARPETA_CON_CAPTURAS

La carpeta debe tener 01-inicio.png ... 14-general.png (1280x720).
capturar_tutorial.py las toma solas y las deja en CARPETA/capturas. El video lleva los textos
escritos encima, sin voz, para que se entienda aunque no haya sonido. Si prefieres grabar tu propio
video, solo reemplaza app/static/tutorial.webm (o agrega tutorial.mp4 en la misma carpeta).
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.render import load_font, wrap_text  # noqa: E402

OUT = ROOT / "app" / "static"
W, H, FPS = 1280, 720, 6
GREEN = (22, 92, 68)

SCENES = [
    ("01-inicio", None, "Inicio te dice qué sigue. Si no sabes por dónde empezar, pulsa el botón verde.", 6.5),
    ("02-grupos", 1, "Paso 1. Crea tu grupo y escribe los nombres de tus alumnos. Se hace una sola vez.", 6.5),
    ("03-pasos", 2, "Paso 2. En Exámenes elige el grupo, la materia y cuál parcial es. Los que ya hiciste salen en verde.", 7.5),
    ("04-series", 2, "Arma el examen con series. Cada serie vale unos puntos y el programa los reparte entre sus preguntas.", 8),
    ("05-vista", 2, "Mira cómo queda la hoja antes de crearla. Cada alumno recibe la suya, con su código QR.", 7),
    ("06-subir", 3, "Paso 3. Escanea las hojas con el celular (Google Drive, Notas o CamScanner), junta todo en un PDF y súbelo aquí.", 9),
    ("07-resultado", 3, "El programa lee el QR de cada página y califica solo. Te avisa a quién le falta una hoja y quién no entregó.", 9),
    ("08-revision", 3, "Si hay preguntas escritas, ves la hoja escaneada y marcas Logrado, Parcial o Aún no.", 8),
    ("09-corregir", 3, "Si una burbuja se leyó mal, la corriges viendo la hoja escaneada y la nota se recalcula sola.", 8),
    ("10-notas", 4, "Paso 4. Las notas de los cuatro bimestres se juntan solas. Descárgalas para Excel.", 6.5),
    ("11-boletin", "+", "Boletines: una hoja por alumno con sus notas del año y qué reforzar, lista para imprimir.", 7),
    ("12-analisis", "+", "Análisis: elige un parcial, una materia o todo el grupo y mira cómo le fue.", 7),
    ("13-alumno", "+", "Cada alumno tiene su texto: qué le falta y qué hacer. Crea su hoja de refuerzo con un botón.", 8),
    ("14-general", "+", "En General ves todas las materias juntas y quién necesita más apoyo.", 6.5),]


def card(title, subtitle):
    image = Image.new("RGB", (W, H), GREEN)
    draw = ImageDraw.Draw(image)
    logo = Image.open(OUT / "logo.png").convert("RGBA").resize((150, 150))
    image.paste(logo, ((W - 150) // 2, 150), logo)
    big, small = load_font(72, bold=True), load_font(36)
    draw.text(((W - draw.textlength(title, font=big)) / 2, 340), title, fill="white", font=big)
    for index, line in enumerate(wrap_text(draw, subtitle, small, 1000)):
        draw.text(((W - draw.textlength(line, font=small)) / 2, 450 + index * 50), line, fill=(205, 232, 218), font=small)
    return np.array(image)[:, :, ::-1]


def caption(base, number, text):
    image = Image.fromarray(base[:, :, ::-1]).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = load_font(36, bold=True)
    lines = wrap_text(draw, text, font, 1020)[:3]
    height = 40 + 46 * len(lines)
    top = H - height - 22
    draw.rounded_rectangle((30, top, W - 30, H - 22), radius=26, fill=(24, 32, 28, 232))
    left = 60
    if number is not None:
        draw.ellipse((52, top + height / 2 - 30, 112, top + height / 2 + 30), fill=(22, 92, 68, 255))
        label = str(number)
        draw.text((82 - draw.textlength(label, font=font) / 2, top + height / 2 - 24), label, fill="white", font=font)
        left = 134
    for index, line in enumerate(lines):
        draw.text((left, top + 20 + index * 46), line, fill="white", font=font)
    return np.array(Image.alpha_composite(image, layer).convert("RGB"))[:, :, ::-1]


def build(shots):
    writer = cv2.VideoWriter(str(OUT / "tutorial.webm"), cv2.VideoWriter_fourcc(*"VP80"), FPS, (W, H))
    if not writer.isOpened():
        raise SystemExit("No se pudo abrir el escritor de video.")
    title = card("Nexam", "Tutorial rápido: de crear el examen a ver qué le falta a cada alumno")
    cv2.imwrite(str(OUT / "tutorial-poster.png"), title)
    end = card("¡Listo para empezar!", "Tus datos están solo en esta computadora y se copian cada día.")
    clips = [(title, 3.5)]
    for name, number, text, seconds in SCENES:
        shot = cv2.imread(str(Path(shots) / f"{name}.png"))
        if shot is None:
            raise SystemExit(f"Falta la captura {name}.png")
        clips.append(((cv2.resize(shot, (W, H)), number, text), seconds))
    clips.append((end, 4.5))

    cache = {}

    def frame_of(clip, progress):
        if isinstance(clip, np.ndarray):
            return clip
        key = id(clip)
        if key not in cache:
            shot, number, text = clip
            cache[key] = caption(shot, number, text)
        return cache[key]

    fade = int(FPS * 0.6)
    previous_last = None
    for clip, seconds in clips:
        count = int(seconds * FPS)
        for index in range(count):
            frame = frame_of(clip, index / max(1, count - 1))
            if previous_last is not None and index < fade:
                alpha = (index + 1) / fade
                frame = cv2.addWeighted(previous_last, 1 - alpha, frame, alpha, 0)
            writer.write(frame)
        previous_last = frame_of(clip, 1.0)
    writer.release()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(sys.argv[1])
    print("Listo: app/static/tutorial.webm")

