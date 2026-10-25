"""Part and parameter specifications. Every generator is registered with a PartSpec, and the API, the planner (LLM) and
the tests all work from these specs, so adding a part means writing one function and one spec."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import re


class ParamError(ValueError):
    """Raised when a parameter value cannot be used (wrong type, unknown choice, bad text)."""


@dataclass
class ParamSpec:
    name: str
    label: str
    kind: str = "float"            # float | int | bool | enum | text
    default: Any = None
    min: float | None = None
    max: float | None = None
    unit: str = "mm"
    help: str = ""
    choices: list[str] | None = None
    max_length: int = 40

    def to_dict(self) -> dict:
        d = {"name": self.name, "label": self.label, "kind": self.kind, "default": self.default, "unit": self.unit, "help": self.help}
        if self.kind in ("float", "int"):
            d["min"], d["max"] = self.min, self.max
        if self.choices:
            d["choices"] = self.choices
        if self.kind == "text":
            d["max_length"] = self.max_length
        return d

    def coerce(self, value: Any, notes: list[str]) -> Any:
        """Convert and clamp one value. Out-of-range numbers are clamped and a note is recorded, never silently changed."""
        if value is None:
            return self.default
        try:
            if self.kind == "bool":
                if isinstance(value, str):
                    return value.strip().lower() in ("1", "true", "yes", "y", "on")
                return bool(value)
            if self.kind == "enum":
                v = str(value).strip().lower()
                if v not in (self.choices or []):
                    raise ParamError(f"{self.name}: '{value}' is not one of {self.choices}")
                return v
            if self.kind == "text":
                v = str(value).strip()
                if len(v) > self.max_length:
                    raise ParamError(f"{self.name}: at most {self.max_length} characters")
                return v
            x = float(value)
            if x != x or x in (float("inf"), float("-inf")):
                raise ParamError(f"{self.name}: not a finite number")
            if self.min is not None and x < self.min:
                notes.append(f"{self.label} {x:g} {self.unit} is below the supported minimum, using {self.min:g} {self.unit}.")
                x = self.min
            if self.max is not None and x > self.max:
                notes.append(f"{self.label} {x:g} {self.unit} is above the supported maximum, using {self.max:g} {self.unit}.")
                x = self.max
            return int(round(x)) if self.kind == "int" else x
        except (TypeError, ValueError) as e:
            if isinstance(e, ParamError):
                raise
            raise ParamError(f"{self.name}: cannot read '{value}' as {self.kind}") from e


@dataclass
class BuildResult:
    """What a generator returns: one or more watertight pieces (name -> Manifold), plus text for the README."""
    pieces: dict[str, Any]
    notes: list[str] = field(default_factory=list)          # things the user should know (adjustments made)
    print_notes: list[str] = field(default_factory=list)    # orientation, supports, material
    fit_notes: list[str] = field(default_factory=list)      # which numbers must be matched to a real object
    derived: dict[str, float] = field(default_factory=dict) # computed sizes worth reporting


@dataclass
class PartSpec:
    id: str
    name: str
    summary: str
    helps: str
    params: list[ParamSpec]
    build: Callable[[dict], BuildResult]
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}

    def resolve(self, given: dict | None) -> tuple[dict, list[str]]:
        """Merge user values over defaults, coerce and clamp. Unknown names are reported, not ignored silently."""
        notes: list[str] = []
        given = dict(given or {})
        out: dict = {}
        for p in self.params:
            out[p.name] = p.coerce(given.pop(p.name, None), notes)
        if given:
            notes.append("Ignored unknown parameters: " + ", ".join(sorted(given)) + ".")
        return out, notes

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "summary": self.summary, "helps": self.helps, "tags": self.tags,
                "params": [p.to_dict() for p in self.params]}


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
