"""Measuring from a photo with a printed reference marker.

The user prints marker.svg at 100 % (a 50 mm ArUco marker plus a 100 mm check line), lays the object on or next to it, and takes a photo
from straight above. The server finds the marker, maps the photo onto the marker's plane (a homography, so moderate tilt is corrected), and
turns pairs of points the user clicked into millimetres, with an honest error estimate.

Limits worth knowing: the answer is only right for points that lie in the marker's plane. A feature 40 mm closer to a camera 400 mm away
reads about 10 % too big, so the API warns when the marker looks small or tilted, and the website asks the user to confirm every value.
A coin or a bank card would also work as a reference, but a coin's edge is hard to find reliably and a card photo can leak card details
to the model provider, so the marker is the only reference supported."""
from __future__ import annotations
import io
import math

import numpy as np

MARKER_ID = 7
MARKER_MM = 50.0                  # printed side length of the black square, border included
CHECK_LINE_MM = 100.0


class MeasureError(ValueError):
    """The photo could not be measured. The message is safe to show."""


def _dictionary():
    import cv2
    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def marker_svg() -> str:
    """An A4 sheet: the marker, a 100 mm check line and short instructions. SVG units are millimetres, so it prints true to size at 100 %."""
    import cv2
    cells = cv2.aruco.generateImageMarker(_dictionary(), MARKER_ID, 6)     # 4x4 data bits plus a one-cell black border
    cell = MARKER_MM / 6
    x0, y0 = (210 - MARKER_MM) / 2, 40.0
    rects = []
    for r in range(6):
        for c in range(6):
            if cells[r * cells.shape[0] // 6, c * cells.shape[1] // 6] < 128:
                rects.append(f'<rect x="{x0 + c * cell:.3f}" y="{y0 + r * cell:.3f}" width="{cell + 0.02:.3f}" height="{cell + 0.02:.3f}"/>')
    ly = y0 + MARKER_MM + 30
    lx = (210 - CHECK_LINE_MM) / 2
    text = [
        "ReForm3D measuring sheet",
        "1. Print at 100 % (turn off 'fit to page'). The line above must measure exactly 100 mm.",
        "2. Lay the object flat on the sheet, next to the square, with the part you want to measure at the same height as the paper.",
        "3. Take the photo from straight above, about 30 to 40 cm away, with the whole square and the object in view.",
        "4. On the website, click the two ends of each distance. Check every value against a ruler before printing a part.",
    ]
    bold = ' font-weight="bold"'
    lines = "".join(f'<text x="20" y="{ly + 22 + i * 8}" font-size="{5 if i == 0 else 3.6}" font-family="sans-serif"{bold if i == 0 else ""}>{t}</text>'
                    for i, t in enumerate(text))
    ticks = "".join(f'<line x1="{lx + i * 10}" y1="{ly - (3 if i % 5 else 5)}" x2="{lx + i * 10}" y2="{ly}" stroke="#000" stroke-width="0.3"/>' for i in range(11))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">'
            f'<rect width="210" height="297" fill="#fff"/><g fill="#000">{"".join(rects)}</g>'
            f'<text x="{x0}" y="{y0 - 4}" font-size="3.5" font-family="sans-serif">Reference marker, {MARKER_MM:g} mm. Keep it flat and uncovered.</text>'
            f'<line x1="{lx}" y1="{ly}" x2="{lx + CHECK_LINE_MM}" y2="{ly}" stroke="#000" stroke-width="0.4"/>{ticks}'
            f'<text x="{lx}" y="{ly + 6}" font-size="3.5" font-family="sans-serif">0</text>'
            f'<text x="{lx + CHECK_LINE_MM - 10}" y="{ly + 6}" font-size="3.5" font-family="sans-serif">100 mm</text>{lines}</svg>')


def _load(image: bytes) -> np.ndarray:
    """Greyscale array in the orientation the browser shows (EXIF rotation applied), so clicked coordinates line up."""
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(image))
        im = ImageOps.exif_transpose(im)
        im.load()
    except Exception:
        raise MeasureError("that file is not a readable image")
    if im.width * im.height > 40_000_000:
        raise MeasureError("the image is too large (over 40 megapixels)")
    return np.asarray(im.convert("L"))


def find_marker(gray: np.ndarray) -> np.ndarray:
    """The marker's four corners in image pixels (top-left, top-right, bottom-right, bottom-left of the printed square)."""
    import cv2
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    det = cv2.aruco.ArucoDetector(_dictionary(), params)
    corners, ids, _ = det.detectMarkers(gray)
    if ids is None:
        raise MeasureError("the reference marker was not found. Print the measuring sheet, keep the whole black square in the photo, "
                           "avoid glare, and take the photo from above.")
    for c, i in zip(corners, ids.flatten()):
        if int(i) == MARKER_ID:
            return c.reshape(4, 2).astype(np.float64)
    raise MeasureError("a marker was found, but it is not the ReForm3D measuring sheet. Print the sheet from this site.")


def measure(image: bytes, segments: list[list[list[float]]]) -> dict:
    """segments: [[[x1, y1], [x2, y2]], ...] in image pixels. Returns the distances in mm with an error estimate and warnings."""
    import cv2
    if not segments or len(segments) > 12:
        raise MeasureError("give between 1 and 12 pairs of points")
    gray = _load(image)
    h_img, w_img = gray.shape
    corners = find_marker(gray)
    plane = np.array([[0, 0], [MARKER_MM, 0], [MARKER_MM, MARKER_MM], [0, MARKER_MM]], dtype=np.float64)
    H, _ = cv2.findHomography(corners, plane)
    if H is None:
        raise MeasureError("the marker was found but its shape could not be used. Retake the photo from straight above.")

    sides = [float(np.linalg.norm(corners[i] - corners[(i + 1) % 4])) for i in range(4)]
    side_px = sum(sides) / 4
    mm_per_px = MARKER_MM / side_px
    distortion = max(sides) / min(sides) - 1                       # 0 for a photo from straight above
    centre = corners.mean(axis=0)

    warnings: list[str] = []
    if side_px < 120:
        warnings.append(f"The marker is only {side_px:.0f} pixels across, so precision is limited. Move closer or use a higher resolution.")
    if distortion > 0.15:
        warnings.append("The photo is taken at an angle. Tilt is corrected for points on the paper, but anything above the paper will be off. "
                        "Take it from straight above for raised features.")

    out = []
    for seg in segments:
        try:
            p = np.asarray(seg, dtype=np.float64).reshape(2, 2)
        except ValueError:
            raise MeasureError("each segment must be two points [[x1, y1], [x2, y2]]")
        if not np.all(np.isfinite(p)) or np.any(p < 0) or np.any(p[:, 0] > w_img) or np.any(p[:, 1] > h_img):
            raise MeasureError("a point lies outside the photo")
        q = cv2.perspectiveTransform(p.reshape(1, 2, 2), H).reshape(2, 2)
        mm = float(np.linalg.norm(q[1] - q[0]))
        # error budget: about 1.5 px for each clicked point, plus the marker's own scale error (about 0.5 px on each corner)
        click = 1.5 * math.sqrt(2) * mm_per_px
        scale = mm * (0.5 * math.sqrt(2) / side_px)
        far = max(float(np.linalg.norm(pt - centre)) for pt in p) / side_px
        err = math.hypot(click, scale) * (1 + 0.5 * max(0.0, far - 2.0))   # points far from the marker are less certain
        out.append({"from": p[0].round(1).tolist(), "to": p[1].round(1).tolist(), "mm": round(mm, 1), "plusminus_mm": round(max(err, 0.2), 1)})
        if far > 4:
            warnings.append(f"A point is {far:.0f} marker-widths from the marker, so that value is less certain. Keep the object close to the square.")
    return {"marker_found": True, "marker_px": round(side_px, 1), "mm_per_px": round(mm_per_px, 4), "tilt": round(distortion, 3),
            "marker_corners": corners.round(1).tolist(), "image_size": [int(w_img), int(h_img)],
            "measurements": out, "warnings": list(dict.fromkeys(warnings)),
            "note": "Only points on the marker's plane are measured correctly. Confirm each value with a ruler before printing."}
