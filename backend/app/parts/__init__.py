"""Part registry. Importing this package registers every generator."""
from __future__ import annotations
from ..spec import PartSpec, ParamSpec

CLEARANCE = ParamSpec("clearance", "Fit clearance", "float", 0.4, 0.0, 1.5, "mm",
                      "Extra room added to every bore and slot so the part slides on. Raise it for a looser fit.")

REGISTRY: dict[str, PartSpec] = {}


def register(spec: PartSpec) -> PartSpec:
    if spec.id in REGISTRY:
        raise ValueError(f"duplicate part id {spec.id}")
    REGISTRY[spec.id] = spec
    return spec


def get(part_id: str) -> PartSpec:
    try:
        return REGISTRY[part_id]
    except KeyError:
        raise KeyError(f"unknown part '{part_id}'. Available: {', '.join(sorted(REGISTRY))}")


from . import lathe_parts, plate_parts, wearables, household, assistive  # noqa: E402,F401  (registration side effects)
