"""A dimensioned drawing of a part, made from its mesh: three orthographic silhouettes (top, front, side) with overall dimensions,
plus a table of the key sizes with where each one came from. SVG units are millimetres, so a part that fits the page prints at 1:1 when
printed at 100 % - handy for holding the paper against the real object."""
from __future__ import annotations
from html import escape

import numpy as np
import trimesh

PAGE_W, PAGE_H = 297.0, 210.0          # A4 landscape
MARGIN, GAP = 12.0, 22.0
SRC = {"user": "you typed it", "measured": "measured from photo", "assumed": "AI estimate - check it", "derived": "computed from the others"}


def _silhouette(mesh: trimesh.Trimesh, axes: tuple[int, int], ppm: float) -> tuple[list[np.ndarray], tuple[float, float, float, float]]:
    """Outline loops (in mm, view coordinates) of the mesh projected onto two axes, traced from a raster of its filled triangles."""
    import cv2
    from PIL import Image, ImageDraw
    v = mesh.vertices[:, list(axes)]
    lo, hi = v.min(axis=0), v.max(axis=0)
    pad = 2
    w, h = int(np.ceil((hi[0] - lo[0]) * ppm)) + 2 * pad, int(np.ceil((hi[1] - lo[1]) * ppm)) + 2 * pad
    img = Image.new("L", (max(w, 3), max(h, 3)), 0)
    draw = ImageDraw.Draw(img)
    px = (v - lo) * ppm + pad
    for tri in px[mesh.faces]:
        draw.polygon([tuple(p) for p in tri], fill=255)
    contours, _ = cv2.findContours(np.asarray(img), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    loops = []
    for c in contours:
        c = cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2).astype(float)
        if len(c) >= 3 and abs(cv2.contourArea(c.astype(np.float32))) > 4:
            loops.append((c - pad) / ppm)                    # back to mm, origin at the view's min corner
    return loops, (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))


def _path(loops: list[np.ndarray], ox: float, oy: float, height: float, flip: bool) -> str:
    d = []
    for loop in loops:
        pts = [(ox + x, oy + (height - y if flip else y)) for x, y in loop]
        d.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z")
    return " ".join(d)


def _dim_h(x0: float, x1: float, y: float, label: str) -> str:
    return (f'<line x1="{x0:.2f}" y1="{y:.2f}" x2="{x1:.2f}" y2="{y:.2f}" class="d" marker-start="url(#a)" marker-end="url(#a)"/>'
            f'<text x="{(x0 + x1) / 2:.2f}" y="{y - 1.2:.2f}" class="t" text-anchor="middle">{label}</text>')


def _dim_v(x: float, y0: float, y1: float, label: str) -> str:
    cy = (y0 + y1) / 2
    return (f'<line x1="{x:.2f}" y1="{y0:.2f}" x2="{x:.2f}" y2="{y1:.2f}" class="d" marker-start="url(#a)" marker-end="url(#a)"/>'
            f'<text x="{x - 1.4:.2f}" y="{cy:.2f}" class="t" text-anchor="middle" transform="rotate(-90 {x - 1.4:.2f} {cy:.2f})">{label}</text>')


def drawing_svg(meshes: dict[str, trimesh.Trimesh], title: str, key_dimensions: list[dict] | None = None) -> str:
    name, mesh = next(iter(meshes.items()))                # the main piece; other pieces are listed by size
    ext = mesh.extents
    views = [("Top view", (0, 1), True), ("Front view", (0, 2), True), ("Side view", (1, 2), True)]
    # layout: front view top-left, side view to its right, top view under the front view (projection in the third-angle style)
    fw, fh = ext[0], ext[2]
    sw, tw, th = ext[1], ext[0], ext[1]
    avail_w = PAGE_W - 2 * MARGIN - 8 - 100 - GAP          # keep a column on the right for the table
    avail_h = PAGE_H - 2 * MARGIN - 16 - 12 - GAP
    scale = min(1.0, avail_w / (fw + sw + 1e-9), avail_h / (fh + th + 1e-9))
    scale = 1.0 if scale >= 1.0 else max(0.05, float(np.floor(scale * 20) / 20) or 0.05)
    ppm = min(12.0, 2400 / max(float(ext.max()), 1.0))
    pos = {"Front view": (MARGIN + 8, MARGIN + 16), "Side view": (MARGIN + 8 + fw * scale + GAP, MARGIN + 16),
           "Top view": (MARGIN + 8, MARGIN + 16 + fh * scale + GAP)}
    body = []
    for label, axes, flip in views:
        loops, (x0, y0, x1, y1) = _silhouette(mesh, axes, ppm)
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        ox, oy = pos[label]
        scaled = [l * scale for l in loops]
        body.append(f'<path d="{_path(scaled, ox, oy, h, flip)}" class="s" fill-rule="evenodd"/>')
        body.append(f'<text x="{ox:.2f}" y="{oy - 9:.2f}" class="v">{label}</text>')
        body.append(_dim_h(ox, ox + w, oy - 3.5, f"{x1 - x0:.1f}"))
        body.append(_dim_v(ox - 3.5, oy, oy + h, f"{y1 - y0:.1f}"))
    # table of key sizes
    tx, ty = PAGE_W - MARGIN - 90, MARGIN + 16
    rows = [f'<text x="{tx}" y="{ty - 9}" class="v">Key sizes (mm)</text>']
    dims = (key_dimensions or [])[:16]
    if not dims:
        rows.append(f'<text x="{tx}" y="{ty}" class="t">Overall {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f}</text>')
    for i, d in enumerate(dims):
        y = ty + i * 9
        flag = " *" if d.get("fits_object") else ""
        rows.append(f'<text x="{tx}" y="{y}" class="t">{escape(str(d["label"]))[:46]}{flag}</text>'
                    f'<text x="{tx + 90}" y="{y}" class="t" text-anchor="end">{float(d["value_mm"]):.1f}</text>'
                    f'<text x="{tx}" y="{y + 3.6}" class="n">{escape(SRC.get(d.get("source", ""), ""))}</text>')
    if dims:
        rows.append(f'<text x="{tx}" y="{ty + len(dims) * 9 + 2}" class="n">* must fit the real object</text>')
    others = [f"{escape(n)}: {m.extents[0]:.1f} x {m.extents[1]:.1f} x {m.extents[2]:.1f}" for n, m in list(meshes.items())[1:]]
    if others:
        rows.append(f'<text x="{tx}" y="{ty + len(dims) * 9 + 10}" class="n">Other pieces: {"; ".join(others)[:120]}</text>')
    foot = (f'Scale {"1:1 when printed at 100 %" if scale == 1.0 else f"1:{1 / scale:.3g} (part larger than the page)"}. '
            f'Silhouettes, so hidden holes do not show. Dimensions in millimetres.')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" viewBox="0 0 {PAGE_W} {PAGE_H}">'
            '<defs><marker id="a" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" markerHeight="4" orient="auto-start-reverse">'
            '<path d="M0,0 L6,3 L0,6 z" fill="#1d3557"/></marker>'
            '<style>.s{fill:#e9eef5;stroke:#1d3557;stroke-width:0.35}.d{stroke:#1d3557;stroke-width:0.2}'
            '.t{font:3.2px sans-serif;fill:#111}.n{font:2.5px sans-serif;fill:#555}.v{font:bold 3.8px sans-serif;fill:#1d3557}'
            '.h{font:bold 5px sans-serif;fill:#111}</style></defs>'
            f'<rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>'
            f'<text x="{MARGIN}" y="{MARGIN}" class="h">{escape(title)[:70]}</text>'
            + "".join(body) + "".join(rows)
            + f'<text x="{MARGIN}" y="{PAGE_H - MARGIN + 4}" class="n">{escape(foot)}</text></svg>')
