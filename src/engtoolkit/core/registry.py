"""
Tool registry.

A *tool* is a calculation exposed to the notebooks and the web app. It has:
- an id like ``"thermo.pipe_pressure_drop"`` (section prefix + name),
- a pydantic input model whose fields carry label, unit, default, bounds and help text,
- a function taking that model and returning a :class:`~engtoolkit.core.results.Result`,
- a cited reference used to validate it (every tool needs a validation test).

The web app builds its menus and forms from :func:`export_schema`, so most new tools need no UI code.

    from pydantic import BaseModel
    from engtoolkit.core.registry import register_tool, Input

    class PipeInputs(BaseModel):
        length: float = Input(50.0, "m", "Pipe length", gt=0)

    @register_tool("thermo.pipe_pressure_drop", "Pipe pressure drop", PipeInputs,
                   reference="Crane TP-410; Colebrook (1939)")
    def pipe_pressure_drop(inputs: PipeInputs) -> PipeDropResult: ...
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field

SECTIONS = {
    "thermo": "Thermodynamics & Fluids",
    "structural": "Structural",
    "electrical": "Electrical",
    "asme": "ASME",
}


def Input(default: Any, unit: str = "", label: str = "", description: str = "",
          json_schema_extra: dict[str, Any] | None = None, **constraints):
    """
    pydantic Field with the metadata the web UI needs: unit (SI), label, help text and optional
    hints in ``json_schema_extra`` such as ``{"choices": "fluids"}`` or ``{"choices": "materials:insulation"}``.
    """
    extra = {"unit": unit, "label": label or None, **(json_schema_extra or {})}
    return Field(default, description=description or label, json_schema_extra=extra, **constraints)


@dataclass
class ToolSpec:
    id: str
    name: str
    inputs: type[BaseModel]
    func: Callable[[Any], Any]
    description: str = ""
    reference: str = ""
    tags: tuple[str, ...] = ()
    custom_page: bool = False  # True when the web app has a hand-written page for it
    charts: Callable[[Any, Any], list] | None = None  # (inputs, result) -> list[Chart]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def section(self) -> str:
        return self.id.split(".", 1)[0]

    def parse(self, inputs: BaseModel | dict | None = None, **kwargs) -> BaseModel:
        if inputs is None:
            return self.inputs(**kwargs)
        if isinstance(inputs, dict):
            return self.inputs(**{**inputs, **kwargs})
        return inputs

    def run(self, inputs: BaseModel | dict | None = None, **kwargs):
        return self.func(self.parse(inputs, **kwargs))

    def make_charts(self, inputs: BaseModel, result) -> list:
        """Charts for a result (empty if the tool defines none)."""
        return list(self.charts(inputs, result)) if self.charts else []

    def schema(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "section": self.section,
            "description": self.description,
            "reference": self.reference,
            "tags": list(self.tags),
            "custom_page": self.custom_page,
            "has_charts": self.charts is not None,
            "inputs": self.inputs.model_json_schema(),
        }


_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(tool_id: str, name: str, inputs: type[BaseModel], *, description: str = "",
                  reference: str = "", tags: tuple[str, ...] = (), custom_page: bool = False,
                  charts: Callable[[Any, Any], list] | None = None):
    """Decorator registering a calculation as a tool. ``charts(inputs, result)`` returns Chart specs."""
    section = tool_id.split(".", 1)[0]
    if section not in SECTIONS or "." not in tool_id:
        raise ValueError(f"Tool id {tool_id!r} must look like '<section>.<name>' with section in {list(SECTIONS)}")
    if not reference:
        raise ValueError(f"Tool {tool_id!r} needs a reference (source it is validated against)")

    def decorator(func):
        if tool_id in _REGISTRY and _REGISTRY[tool_id].func is not func:
            raise ValueError(f"Tool {tool_id!r} is already registered")
        _REGISTRY[tool_id] = ToolSpec(tool_id, name, inputs, func, description or (func.__doc__ or "").strip(),
                                      reference, tuple(tags), custom_page, charts)
        return func

    return decorator


def load_tools(sections: list[str] | None = None) -> None:
    """Import the ``tools`` module of each discipline so their tools register."""
    for section in sections or SECTIONS:
        try:
            importlib.import_module(f"engtoolkit.{section}.tools")
        except ModuleNotFoundError as err:
            if err.name != f"engtoolkit.{section}.tools":
                raise


def get_tool(tool_id: str) -> ToolSpec:
    if tool_id not in _REGISTRY:
        load_tools([tool_id.split(".", 1)[0]])
    try:
        return _REGISTRY[tool_id]
    except KeyError:
        raise KeyError(f"Unknown tool {tool_id!r}. Available: {sorted(_REGISTRY)}") from None


def list_tools(section: str | None = None) -> list[ToolSpec]:
    load_tools([section] if section else None)
    return [t for t in _REGISTRY.values() if section is None or t.section == section]


def run(tool_id: str, inputs: BaseModel | dict | None = None, **kwargs):
    """Run a registered tool: ``run("thermo.pipe_pressure_drop", length=100)``."""
    return get_tool(tool_id).run(inputs, **kwargs)


def export_schema() -> dict[str, Any]:
    """JSON-serialisable description of every tool, used to build the web UI."""
    from engtoolkit import __version__
    load_tools()
    return {
        "version": __version__,
        "sections": SECTIONS,
        "tools": [t.schema() for t in sorted(_REGISTRY.values(), key=lambda t: t.id)],
    }
