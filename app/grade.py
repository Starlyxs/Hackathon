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


# El QR impreso es versión 1 (21 módulos) más un borde quieto de 2. El detector
# devuelve solo los módulos negros; hay que expandirlos hasta el cuadro impreso.
_QR_PRINT_SCALE = 25.0 / 21.0


def _payload(value):
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if not isinstance(value, str) or not value.startswith("EDU1:"):
        return None
    return value.split(":", 1)[1]


def _points_of(points, scale):
    if points is None:
        return None
    arr = np.array(points, dtype=np.float32).reshape(-1, 2)
    if arr.shape[0] < 4:
        return None
    return arr[:4] / float(scale)


def _detect_with(detector, image, scale):
    try:
        value, points, _ = detector.detectAndDecode(image)
    except cv2.error:
        value, points = "", None
    sheet_id = _payload(value)
    found = _points_of(points, scale)
    if sheet_id and found is not None:
        return sheet_id, found
    try:
        ok, decoded, points, _ = detector.detectAndDecodeMulti(image)
    except cv2.error:
        return None
    if not ok or decoded is None:
        return None
    arr = np.array(points) if points is not None else None
    for index, text in enumerate(decoded):
        sheet_id = _payload(text)
        if not sheet_id or arr is None:
            continue
        quad = arr[index] if arr.ndim == 3 else arr
        found = _points_of(quad, scale)
        if found is not None:
            return sheet_id, found
    return None


def find_qr(bgr):
    """Busca el QR en la foto completa, antes de enderezar la hoja."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    variants = (bgr, gray, clahe)
    long_side = max(bgr.shape[:2])
    scales = [1.0]
    if long_side < 1400:
        scales.append(2.0)
    if long_side < 800:
        scales.append(3.0)
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        try:
            detectors.append(cv2.QRCodeDetectorAruco())
        except cv2.error:
            pass
    for detector in detectors:
        for image in variants:
            for scale in scales:
                picture = image if scale == 1 else cv2.resize(
                    image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )
                found = _detect_with(detector, picture, scale)
                if found:
                    return found
    return None, None


def quick_sheet_id(bgr):
    """Lectura rápida del QR para la cámara en vivo. No endereza ni califica."""
    long_side = max(bgr.shape[:2])
    if long_side > 1000:
        factor = 1000.0 / long_side
        bgr = cv2.resize(bgr, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        try:
            detectors.append(cv2.QRCodeDetectorAruco())
        except cv2.error:
            pass
    for detector in detectors:
        found = _detect_with(detector, gray, 1.0)
        if found:
            return found[0]
    return None


def _quad_ok(corners, shape):
    pts = np.array(corners, dtype=np.float32).reshape(4, 2)
    if not cv2.isContourConvex(np.round(pts).astype(np.int32).reshape(-1, 1, 2)):
        return False
    area = cv2.contourArea(pts.reshape(-1, 1, 2))
    if area < shape[0] * shape[1] * 0.18:
        return False
    width = (np.linalg.norm(pts[1] - pts[0]) + np.linalg.norm(pts[2] - pts[3])) / 2
    height = (np.linalg.norm(pts[3] - pts[0]) + np.linalg.norm(pts[2] - pts[1])) / 2
    if height < 1:
        return False
    return 0.55 <= width / height <= 0.95


def _page_candidates(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    binaries = []
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    binaries.append(cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel))
    _, bright = cv2.threshold(blur, 170, 255, cv2.THRESH_BINARY)
    binaries.append(cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel))
    quads = []
    image_area = bgr.shape[0] * bgr.shape[1]
    for binary in binaries:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            if cv2.contourArea(contour) < image_area * 0.18:
                break
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) != 4:
                continue
            quad = _order_corners(approx)
            if _quad_ok(quad, bgr.shape):
                quads.append(quad)
    return quads


def _solid_squares(bgr):
    """Cuadros negros macizos. Los del QR tienen un cuadrado dentro y se descartan."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    hierarchy = hierarchy[0]
    image_area = bgr.shape[0] * bgr.shape[1]
    found = []
    for index, contour in enumerate(contours):
        child, parent = hierarchy[index][2], hierarchy[index][3]
        if child != -1 or parent != -1:
            continue
        area = cv2.contourArea(contour)
        if area < image_area * 0.00025 or area > image_area * 0.02:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if h == 0 or not 0.75 <= w / float(h) <= 1.35:
            continue
        if area / float(w * h) < 0.72:
            continue
        found.append((x + w / 2.0, y + h / 2.0, area))
    return found


def _four_extremes(found):
    pts = [(x, y) for x, y, _ in found]
    keys = (
        lambda p: p[0] + p[1],
        lambda p: p[1] - p[0],
        lambda p: -(p[0] + p[1]),
        lambda p: p[0] - p[1],
    )
    used = set()
    picks = []
    for key in keys:
        best_i = None
        best_v = None
        for index, point in enumerate(pts):
            if index in used:
                continue
            value = key(point)
            if best_v is None or value < best_v:
                best_v = value
                best_i = index
        if best_i is None:
            return None
        used.add(best_i)
        picks.append(pts[best_i])
    return np.float32(picks)


def _marker_corners(bgr):
    found = _solid_squares(bgr)
    if len(found) < 4:
        return None
    biggest = max(area for _, _, area in found)
    found = [item for item in found if item[2] >= biggest * 0.35]
    if len(found) < 4:
        return None
    corners = _four_extremes(found)
    if corners is None or not _quad_ok(corners, bgr.shape):
        return None
    return corners


def _qr_page_corners(qr_pts):
    # El detector entrega las esquinas en el orden de la hoja, aunque la foto esté girada.
    ordered = np.array(qr_pts, dtype=np.float32).reshape(4, 2)
    center = ordered.mean(axis=0)
    printed = center + (ordered - center) * _QR_PRINT_SCALE
    src = np.float32(
        [
            [QR_XY[0], QR_XY[1]],
            [QR_XY[0] + QR_SIZE - 1, QR_XY[1]],
            [QR_XY[0] + QR_SIZE - 1, QR_XY[1] + QR_SIZE - 1],
            [QR_XY[0], QR_XY[1] + QR_SIZE - 1],
        ]
    )
    matrix = cv2.getPerspectiveTransform(src, np.float32(printed))
    page = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]]).reshape(1, 4, 2)
    return cv2.perspectiveTransform(page, matrix).reshape(4, 2)


def _warp(bgr, corners, destination):
    matrix = cv2.getPerspectiveTransform(np.float32(corners), np.float32(destination))
    return cv2.warpPerspective(bgr, matrix, (W, H), flags=cv2.INTER_CUBIC)


def _alignment_score(aligned):
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    score = 0.0
    for x, y in marker_centers().values():
        xi, yi = int(x), int(y)
        patch = gray[max(0, yi - 14) : yi + 14, max(0, xi - 14) : xi + 14]
        if patch.size and float(np.mean(patch)) < 95:
            score += 2.0
    x, y = QR_XY
    crop = gray[y + 16 : y + QR_SIZE - 16, x + 16 : x + QR_SIZE - 16]
    if crop.size:
        score += min(float(np.std(crop)) / 35.0, 2.0)
    return score


def align_sheet(bgr, qr_pts=None):
    page_dest = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
    jobs = [(quad, page_dest) for quad in _page_candidates(bgr)]
    markers = _marker_corners(bgr)
    if markers is not None:
        order = ("tl", "tr", "br", "bl")
        jobs.append((markers, np.float32([marker_centers()[name] for name in order])))
    if qr_pts is not None:
        try:
            jobs.append((_qr_page_corners(qr_pts), page_dest))
        except cv2.error:
            pass
    best = None
    best_score = -1.0
    for corners, destination in jobs:
        aligned = _warp(bgr, corners, destination)
        score = _alignment_score(aligned)
        if score > best_score:
            best_score = score
            best = aligned
    if best is None or best_score < 6:
        raise GradeError(
            "No encontré la hoja completa. Ponla sobre un fondo liso, deja visibles las cuatro esquinas negras y acerca el QR."
        )
    return best


def read_sheet_id(aligned):
    x, y = QR_XY
    pad = 90
    crop = aligned[max(0, y - pad) : y + QR_SIZE + pad, max(0, x - pad) : x + QR_SIZE + pad]
    for image in (crop, aligned):
        sheet_id, _ = find_qr(image)
        if sheet_id:
            return sheet_id
    raise GradeError(
        "Leí la hoja, pero no el código QR. Sostén la cámara quieta, sin flash, y haz que el QR se vea grande."
    )


def read_photo(bgr):
    sheet_id, qr_pts = find_qr(bgr)
    aligned = align_sheet(bgr, qr_pts)
    if not sheet_id:
        sheet_id = read_sheet_id(aligned)
    return aligned, sheet_id


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
