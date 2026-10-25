"""Optional slicer-in-the-loop: ask a real slicer (PrusaSlicer, headless) how the part would print.

The geometric overhang survey in printability.py is a fast heuristic. A slicer is the ground truth: it says how many minutes and how much plastic
the part takes and how much of that is support. When no slicer is installed everything here quietly steps aside and the heuristic estimate is used.
The slicer's own G-code is thrown away; only its numbers are kept."""
from __future__ import annotations
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

from .printability import Material, profile_for

log = logging.getLogger("reform3d.slicer")
CANDIDATES = ("prusa-slicer", "prusa-slicer-console", "PrusaSlicer", "prusaslicer")
FILAMENT_DIAMETER = 1.75
SUPPORT_SHARE_WARN = 0.15          # support plastic above this share of the part is worth telling the designer about
SUPPORT_MIN_CM3 = 0.5

NOZZLE_TEMP = {"pla": (210, 60), "petg": (240, 80), "abs": (250, 100), "tpu": (225, 50), "nylon": (260, 80)}
SLOW_MATERIAL = ("--perimeter-speed", "25", "--external-perimeter-speed", "20", "--small-perimeter-speed", "15", "--infill-speed", "30",
                 "--solid-infill-speed", "25", "--top-solid-infill-speed", "20", "--bridge-speed", "20", "--max-volumetric-speed", "3", "--retract-length", "0")


@dataclass
class SliceResult:
    ok: bool
    minutes: float = 0.0
    filament_cm3: float = 0.0
    filament_g: float = 0.0
    support_cm3: float = 0.0
    support_share: float = 0.0
    layers: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def find_slicer(setting: str = "auto") -> str | None:
    """Path of a PrusaSlicer binary, or None. setting: 'off' disables, 'auto' searches PATH, anything else is taken as a path."""
    s = (setting or "auto").strip()
    if s.lower() in ("off", "none", "false", "0", "no"):
        return None
    if s.lower() != "auto":
        return s if os.path.isfile(s) and os.access(s, os.X_OK) else shutil.which(s)
    for name in CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


@lru_cache(maxsize=8)
def slicer_version(binary: str) -> str:
    try:
        out = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=20, env=_env(tempfile.gettempdir())).stdout
    except Exception:
        return "slicer"
    m = re.search(r"(PrusaSlicer-[\d.]+\w*)", out)
    return m.group(1) if m else "slicer"


def _env(home: str) -> dict:
    return {"HOME": home, "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C", "LANG": "C"}


def _time_to_minutes(text: str) -> float:
    total = 0.0
    for value, unit in re.findall(r"(\d+)\s*([dhms])", text):
        total += int(value) * {"d": 1440.0, "h": 60.0, "m": 1.0, "s": 1 / 60.0}[unit]
    return total


def parse_gcode(text: str, density: float) -> SliceResult:
    """Read the numbers out of PrusaSlicer's G-code: total time, plastic, and plastic spent on support (per ';TYPE:' sections, relative extrusion)."""
    feature = ""
    support_mm = 0.0
    total_mm = 0.0
    layers = 0
    minutes = 0.0
    for line in text.splitlines():
        if line.startswith(";TYPE:"):
            feature = line[6:].strip().lower()
        elif line.startswith(";LAYER_CHANGE"):
            layers += 1
        elif line.startswith("G1") and " E" in line and (" X" in line or " Y" in line):      # moves that print; a bare "G1 E.." only pushes filament back after a retraction
            m = re.search(r" E(-?[\d.]+)", line)
            if m:
                e = float(m.group(1))
                if e > 0:
                    total_mm += e
                    if "support" in feature:
                        support_mm += e
        elif line.startswith("; estimated printing time (normal mode)"):
            minutes = _time_to_minutes(line.split("=", 1)[1])
    area = math.pi * (FILAMENT_DIAMETER / 2) ** 2
    cm3, sup = total_mm * area / 1000.0, support_mm * area / 1000.0
    if layers == 0 or total_mm <= 0:
        return SliceResult(False, error="the slicer produced no layers")
    return SliceResult(True, minutes=round(minutes, 1), filament_cm3=round(cm3, 3), filament_g=round(cm3 * density, 2), support_cm3=round(sup, 3),
                       support_share=round(sup / cm3, 3) if cm3 else 0.0, layers=layers)  # share from the unrounded volumes


def slice_stl(stl: Path, material: Material | str | None, bed: tuple[float, float, float], binary: str, timeout: float = 60.0) -> SliceResult:
    """Slice one STL (already sitting on z = 0) at 0.2 mm layers, 3 walls, 20 % infill, automatic supports, with the material's temperatures and speeds."""
    mat = material if isinstance(material, Material) else profile_for(material)
    nozzle, bedt = NOZZLE_TEMP.get(mat.key, (210, 60))
    with tempfile.TemporaryDirectory(prefix="reform3d-slice-") as td:
        out = Path(td) / "out.gcode"
        cmd = [binary, "--export-gcode", "--dont-arrange", "--center", f"{bed[0] / 2:g},{bed[1] / 2:g}", "--output", str(out),
               "--bed-shape", f"0x0,{bed[0]:g}x0,{bed[0]:g}x{bed[1]:g},0x{bed[1]:g}", "--max-print-height", f"{bed[2]:g}",
               "--layer-height", "0.2", "--first-layer-height", "0.2", "--perimeters", "3", "--fill-density", "20%", "--top-solid-layers", "5", "--bottom-solid-layers", "4",
               "--nozzle-diameter", "0.4", "--filament-diameter", str(FILAMENT_DIAMETER), "--filament-density", str(mat.density),
               "--temperature", str(nozzle), "--first-layer-temperature", str(nozzle), "--bed-temperature", str(bedt), "--first-layer-bed-temperature", str(bedt),
               "--use-relative-e-distances", "--support-material", "--support-material-auto", "--loglevel", "1", *(SLOW_MATERIAL if mat.flexible else ()), str(stl)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env(td))
        except subprocess.TimeoutExpired:
            return SliceResult(False, error=f"the slicer took longer than {timeout:g} s")
        except OSError as e:
            return SliceResult(False, error=f"the slicer could not be started ({e})")
        if proc.returncode != 0 or not out.exists():
            msg = (proc.stderr or proc.stdout or "").strip().splitlines()
            return SliceResult(False, error=("the slicer rejected the model: " + (msg[-1] if msg else f"exit code {proc.returncode}"))[:300])
        return parse_gcode(out.read_text(errors="replace"), mat.density)


def slice_meshes(meshes: dict, material: Material | str | None, bed, binary: str, timeout: float = 60.0, limit: int = 4) -> dict[str, SliceResult]:
    """Slice every piece (up to `limit`) and return {piece name: result}."""
    results: dict[str, SliceResult] = {}
    with tempfile.TemporaryDirectory(prefix="reform3d-pieces-") as td:
        for i, (name, tm) in enumerate(meshes.items()):
            if i >= limit:
                break
            path = Path(td) / f"p{i}.stl"
            path.write_bytes(tm.export(file_type="stl"))
            results[name] = slice_stl(path, material, bed, binary, timeout)
    return results


def combine(results: dict[str, SliceResult]) -> SliceResult | None:
    """One result for the whole job (print time and plastic add up); None when any piece failed to slice."""
    if not results or not all(r.ok for r in results.values()):
        return None
    cm3 = sum(r.filament_cm3 for r in results.values())
    sup = sum(r.support_cm3 for r in results.values())
    return SliceResult(True, minutes=round(sum(r.minutes for r in results.values()), 1), filament_cm3=round(cm3, 3), filament_g=round(sum(r.filament_g for r in results.values()), 2),
                       support_cm3=round(sup, 3), support_share=round(sup / cm3, 3) if cm3 else 0.0, layers=sum(r.layers for r in results.values()))


def support_warning(res: SliceResult, material: Material) -> str | None:
    if res.ok and res.support_share > SUPPORT_SHARE_WARN and res.support_cm3 > SUPPORT_MIN_CM3:
        return (f"the slicer adds {res.support_cm3:.1f} cm3 of support ({res.support_share * 100:.0f}% of all the plastic) to print this in {material.name} "
                "as modelled: remove the overhangs, add a chamfer under hanging features or a flat base, or turn the part so its widest face is on the bed")
    return None
