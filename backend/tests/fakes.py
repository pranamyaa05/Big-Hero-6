"""A scripted stand-in for the model, in the shape of the Anthropic Messages API, so the whole design loop can be tested offline."""
from __future__ import annotations
import types
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "app" / "design_examples"


def example_code(name: str) -> str:
    return (EXAMPLES / f"{name}.py").read_text()


def tool_use(name: str, data: dict, id: str = "tu_1"):
    return types.SimpleNamespace(type="tool_use", name=name, input=data, id=id)


def submit(code: str, title: str = "Test part", **extra):
    data = {"title": title, "understanding": "Test understanding.", "code": code, "assumptions": ["size 10 mm (assumed)"],
            "print_notes": ["Print flat."], "fit_notes": ["Measure it."]}
    data.update(extra)
    return tool_use("submit_design", data)


def accept():
    return tool_use("accept_design", {"checked": "looks right"})


class _Messages:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def create(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})     # snapshot: the caller keeps appending to its list
        if not self.responses:
            raise AssertionError("the scripted model ran out of answers")
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return types.SimpleNamespace(content=r if isinstance(r, list) else [r], stop_reason="tool_use")


class FakeClient:
    def __init__(self, *responses):
        self.messages = _Messages(responses)

    @property
    def calls(self):
        return self.messages.calls
