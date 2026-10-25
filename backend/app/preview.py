"""Dependency-light preview renderer: orthographic, depth-sorted, back-face culled, flat shaded, drawn with Pillow."""
from __future__ import annotations
import io
import math
import numpy as np
import trimesh
from PIL import Image, ImageDraw

BG = (244, 242, 238)
BASE = np.array([232, 112, 28], dtype=np.float64)       # orange, like the parts in the reference photos


def _rot(az_deg: float, el_deg: float) -> np.ndarray:
    """Rows are the camera's right, up and towards-the-viewer axes in model space (Z is up in the model)."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    c = np.array([math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)])
    right = np.cross([0, 0, 1.0], c)
    right /= np.linalg.norm(right)
    up = np.cross(c, right)
    return np.vstack([right, up, c])


def layout(pieces: dict[str, trimesh.Trimesh], gap: float = 12.0) -> list[trimesh.Trimesh]:
    """Place pieces side by side along X, centred, so a multi-part job shows in one picture or one GLB."""
    out, x = [], 0.0
    for tm in pieces.values():
        t = tm.copy()
        b = t.bounds
        t.apply_translation([x - b[0][0], -(b[0][1] + b[1][1]) / 2, 0])
        x += t.extents[0] + gap
        out.append(t)
    total = x - gap
    for t in out:
        t.apply_translation([-total / 2, 0, 0])
    return out


def render_png(pieces: dict[str, trimesh.Trimesh], size: int = 720, az: float = -38, el: float = 62, scale_up: int = 2) -> bytes:
    meshes = layout(pieces)
    allv = np.vstack([m.vertices for m in meshes])
    R = _rot(az, el)
    S = size * scale_up
    pv = allv @ R.T
    xmin, xmax = pv[:, 0].min(), pv[:, 0].max()
    ymin, ymax = pv[:, 1].min(), pv[:, 1].max()
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    k = 0.84 * S / span
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    light = np.array([0.35, -0.45, 0.82]); light /= np.linalg.norm(light)
    img = Image.new("RGB", (S, S), BG)
    dr = ImageDraw.Draw(img)
    polys = []
    for m in meshes:
        v = m.vertices @ R.T
        f = m.faces
        n = m.face_normals @ R.T
        vis = n[:, 2] > 0                          # camera looks down -z in view space; faces with +z normals face the viewer
        depth = v[f, 2].mean(axis=1)
        sh = np.clip(n @ light, 0, 1)
        for i in np.nonzero(vis)[0]:
            polys.append((depth[i], f[i], v, sh[i]))
    polys.sort(key=lambda t: t[0])
    for depth, face, v, s in polys:
        pts = [((v[j, 0] - cx) * k + S / 2, S / 2 - (v[j, 1] - cy) * k) for j in face]
        col = tuple(int(c) for c in np.clip(BASE * (0.38 + 0.72 * s), 0, 255))
        dr.polygon(pts, fill=col, outline=col)
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
