"""Coordenadas únicas de la hoja. Se dibuja y se califica con los mismos números."""

W = 1200
H = 1697
MARKER = 64
MARKER_INSET = 44
QR_XY = (760, 168)
QR_SIZE = 250
BUBBLE_R = 18
N_QUESTIONS = 8
OPTIONS_X = (180, 432, 684, 936)
OPTION_LETTERS = ("A", "B", "C", "D")


def marker_boxes():
    size = MARKER
    inset = MARKER_INSET
    return {
        "tl": (inset, inset, size, size),
        "tr": (W - inset - size, inset, size, size),
        "br": (W - inset - size, H - inset - size, size, size),
        "bl": (inset, H - inset - size, size, size),
    }


def marker_centers():
    centers = {}
    for name, (x, y, w, h) in marker_boxes().items():
        centers[name] = (x + w / 2.0, y + h / 2.0)
    return centers


def question_slots(n=N_QUESTIONS):
    slots = []
    y0 = 468
    stride = 136
    for i in range(n):
        y = y0 + i * stride
        slots.append(
            {
                "prompt": (72, y),
                "bubbles": [(x, y + 74) for x in OPTIONS_X],
            }
        )
    return slots
