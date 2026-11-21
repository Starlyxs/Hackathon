"""Encuentra la hoja, lee el QR y decide qué burbuja está llena."""

import cv2
import numpy as np

from app.layout import BUBBLE_R, H, QR_SIZE, QR_XY, W, marker_centers, question_slots

MARK_THRESHOLD = 165


class GradeError(Exception):
    pass


def pil_to_bgr(image):
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def mark_bubbles(bgr, choices):
    """choices: índice 0-3, o None si esa pregunta queda en blanco."""
    out = bgr.copy()
    slots = question_slots(len(choices))
    for choice, slot in zip(choices, slots):
        if choice is None:
            continue
        x, y = slot["bubbles"][choice]
        cv2.circle(out, (int(x), int(y)), BUBBLE_R - 5, (20, 24, 22), -1)
    return out


def simulate_photo(bgr, seed=0):
    """Perspectiva, escritorio gris y JPEG, parecido a una webcam modesta."""
    rng = np.random.default_rng(seed)
    height, width = bgr.shape[:2]
    pad = 90
    canvas_w = width + pad * 2
    canvas_h = height + pad * 2
    src = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])

    def jitter(x, y):
        return [
            x + float(rng.integers(-28, 29)),
            y + float(rng.integers(-28, 29)),
        ]

    dst = np.float32(
        [
            jitter(pad, pad),
            jitter(width + pad - 1, pad),
            jitter(width + pad - 1, height + pad - 1),
            jitter(pad, height + pad - 1),
        ]
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    desk = np.full((canvas_h, canvas_w, 3), 146, np.uint8)
    noise = rng.integers(0, 22, desk.shape, dtype=np.uint8)
    desk = cv2.subtract(desk, noise)
    warped = cv2.warpPerspective(bgr, matrix, (canvas_w, canvas_h))
    mask = cv2.warpPerspective(np.full((height, width), 255, np.uint8), matrix, (canvas_w, canvas_h))
    desk[mask > 0] = warped[mask > 0]
    small = cv2.resize(desk, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
    if not ok:
        raise GradeError("No pude simular la foto.")
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def _order_corners(pts):
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    total = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    return np.float32(
        [
            pts[np.argmin(total)],
            pts[np.argmin(diff)],
            pts[np.argmax(total)],
            pts[np.argmax(diff)],
        ]
    )


def _page_corners(bgr):
    """La hoja blanca sobre la mesa es más estable que los cuadritos del QR."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = bgr.shape[0] * bgr.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:6]:
        area = cv2.contourArea(contour)
        if area < image_area * 0.25:
            return None
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            return _order_corners(approx)
    return None


def _marker_corners(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = bgr.shape[0] * bgr.shape[1]
    found = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.0004 or area > image_area * 0.02:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if h == 0 or not 0.8 <= w / float(h) <= 1.25:
            continue
        if area / float(w * h) < 0.8:
            continue
        found.append((x + w / 2.0, y + h / 2.0, area))
    if len(found) < 4:
        return None
    height, width = bgr.shape[:2]
    targets = ((0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1))
    limit = (min(width, height) * 0.22) ** 2
    chosen = []
    used = set()
    for target in targets:
        best_i = None
        best_d = None
        for i, (x, y, _) in enumerate(found):
            if i in used:
                continue
            dist = (x - target[0]) ** 2 + (y - target[1]) ** 2
            if best_d is None or dist < best_d:
                best_d = dist
                best_i = i
        if best_i is None or best_d > limit:
            return None
        used.add(best_i)
        chosen.append(found[best_i][:2])
    return np.float32(chosen)


def align_sheet(bgr):
    corners = _page_corners(bgr)
    if corners is not None:
        destination = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
    else:
        corners = _marker_corners(bgr)
        if corners is None:
            raise GradeError("No encontré la hoja completa. Ponla sobre un fondo liso y no tapes las esquinas.")
        order = ("tl", "tr", "br", "bl")
        destination = np.float32([marker_centers()[name] for name in order])
    matrix = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(bgr, matrix, (W, H), flags=cv2.INTER_LINEAR)


def read_sheet_id(aligned):
    detector = cv2.QRCodeDetector()
    x, y = QR_XY
    crop = aligned[y : y + QR_SIZE, x : x + QR_SIZE]
    bigger = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    for image in (bigger, crop, aligned):
        value, _, _ = detector.detectAndDecode(image)
        if value and value.startswith("EDU1:"):
            return value.split(":", 1)[1]
    raise GradeError("Leí la hoja, pero no el código QR. Evita brillos y acerca un poco la cámara.")


def _darkness(gray, x, y):
    mask = np.zeros(gray.shape, np.uint8)
    cv2.circle(mask, (int(x), int(y)), BUBBLE_R - 7, 255, -1)
    return float(cv2.mean(gray, mask=mask)[0])


def read_bubbles(aligned, n_questions):
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    choices = []
    details = []
    for slot in question_slots(n_questions):
        scores = [_darkness(gray, x, y) for x, y in slot["bubbles"]]
        order = sorted(range(len(scores)), key=lambda i: scores[i])
        darkest = order[0]
        filled = [i for i in order if scores[i] < MARK_THRESHOLD]
        if not filled:
            choices.append(None)
            details.append({"status": "vacia", "scores": [round(s, 1) for s in scores]})
            continue
        if len(filled) >= 2 and scores[order[1]] - scores[darkest] < 28:
            choices.append(None)
            details.append({"status": "ambigua", "scores": [round(s, 1) for s in scores]})
            continue
        choices.append(darkest)
        details.append({"status": "marcada", "scores": [round(s, 1) for s in scores]})
    return choices, details
