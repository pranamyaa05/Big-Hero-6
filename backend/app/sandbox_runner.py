"""Runs inside the sandbox subprocess: executes validated CAD code with a restricted namespace and writes the pieces to an .npz file.
usage (internal): python -I app/sandbox_runner.py OUT_NPZ < json{code, cpu_s, memory_mb}
This is defence in depth, not a security boundary: see README, run the service in a container with no network access."""
from __future__ import annotations
import json
import math
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # -I drops the script folder, so add the project root back


def _limits(cpu_s: int, memory_mb: int) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (200 * 1024 * 1024, 200 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except Exception:
        pass                       # non-Linux platforms: the parent's wall-clock timeout still applies


SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n) for n in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "map", "max", "min", "pow", "range",
    "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip", "isinstance", "ValueError", "Exception", "True", "False", "None")}


def main() -> None:
    spec = json.loads(sys.stdin.read())
    out_path = sys.argv[1]
    _limits(int(spec.get("cpu_s", 20)), int(spec.get("memory_mb", 1536)))
    import numpy as np
    from manifold3d import Manifold, CrossSection, JoinType
    from app import geom as g

    np_ns = types.SimpleNamespace(**{n: getattr(np, n) for n in (
        "array", "arange", "linspace", "sin", "cos", "tan", "arctan2", "arccos", "arcsin", "sqrt", "hypot", "abs", "maximum", "minimum",
        "clip", "where", "exp", "log", "power", "pi", "stack", "concatenate", "zeros", "ones", "zeros_like", "ones_like", "mod", "floor", "ceil",
        "deg2rad", "rad2deg", "cumsum", "sign", "round", "isfinite")})
    math_ns = types.SimpleNamespace(**{n: getattr(math, n) for n in (
        "sin", "cos", "tan", "atan2", "acos", "asin", "atan", "sqrt", "hypot", "pi", "tau", "exp", "log", "floor", "ceil", "radians", "degrees", "fabs", "pow")})
    helpers = {n: getattr(g, n) for n in (
        "poly", "circle", "ellipse", "rect", "rrect", "polar", "star", "spline", "tri_wave", "bezier", "smoothstep", "extrude", "cyl", "box",
        "dome", "lathe", "radial", "union", "along_y", "SEG", "hull", "tube", "torus", "capsule", "rounded_box", "array_polar", "array_linear",
        "round_corners", "loft")}

    def lib(part_id, **params):
        """Call one of the tested catalog generators as a building block; returns {piece name: Manifold}."""
        from app import parts as registry
        try:
            spec = registry.get(part_id)
            resolved, _ = spec.resolve(params)
            return dict(spec.build(resolved).pieces)
        except KeyError as e:
            raise ValueError(str(e).strip("'\""))

    ns = {"__builtins__": SAFE_BUILTINS, "np": np_ns, "math": math_ns, "Manifold": Manifold, "CrossSection": CrossSection, "JoinType": JoinType,
          "lib": lib, **helpers}
    exec(compile(spec["code"], "<design>", "exec"), ns)
    if "build" not in ns or not callable(ns["build"]):
        raise ValueError("the code must define build()")
    import inspect
    params = spec.get("params") or {}

    def call(fn):
        accepted = inspect.signature(fn).parameters
        return fn(**{k: v for k, v in params.items() if k in accepted})
    res = call(ns["build"])
    if isinstance(res, Manifold):
        res = {"part": res}
    fit = None
    if callable(ns.get("fit_test")):                      # optional: a small print of only the part that must fit the real object
        fit = call(ns["fit_test"])
        if isinstance(fit, dict):
            fit = list(fit.values())[0] if len(fit) == 1 else None
        if not isinstance(fit, Manifold) or fit.is_empty():
            raise ValueError("fit_test() must return one non-empty Manifold")
    if not isinstance(res, dict) or not res or len(res) > 6:
        raise ValueError("build() must return a Manifold or a dict of 1 to 6 named Manifolds")
    arrays = {}
    names = []
    for i, (name, m) in enumerate(res.items()):
        if str(name).startswith("_"):
            raise ValueError("piece names must not start with '_'")
        if not isinstance(m, Manifold):
            raise ValueError(f"piece '{name}' is not a Manifold")
        if m.is_empty():
            raise ValueError(f"piece '{name}' is empty")
        mesh = m.to_mesh()
        if len(mesh.tri_verts) > 400_000:
            raise ValueError(f"piece '{name}' has {len(mesh.tri_verts)} triangles; reduce circular segments or repeated details (limit 400000)")
        v = np.asarray(mesh.vert_properties)[:, :3]
        if float(np.max(np.abs(v))) > 600:
            raise ValueError(f"piece '{name}' is larger than 600 mm; check the units (millimetres)")
        arrays[f"v{i}"] = v.astype(np.float64)
        arrays[f"f{i}"] = np.asarray(mesh.tri_verts).astype(np.int64)
        names.append(str(name)[:40])
    if fit is not None:
        mesh = fit.to_mesh()
        if len(mesh.tri_verts) > 200_000:
            raise ValueError("fit_test() has too many triangles (limit 200000)")
        i = len(names)
        arrays[f"v{i}"] = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
        arrays[f"f{i}"] = np.asarray(mesh.tri_verts).astype(np.int64)
        names.append("_fit_test")
    np.savez(out_path, **arrays)
    sys.stdout.write(json.dumps({"names": names}))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:                      # report any failure as one clean line for the caller, with the design's line number
        import traceback
        frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == "<design>"]
        where = f" (line {frames[-1].lineno})" if frames else ""
        sys.stderr.write(f"{e.__class__.__name__}: {e}{where}")
        sys.exit(3)
