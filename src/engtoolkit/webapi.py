"""
JSON interface used by the web app's Pyodide worker (and handy for any other front end).

Every function takes and returns JSON strings, so the JavaScript side never handles Python objects.
NaN/inf become null (JSON has no NaN).
"""
from __future__ import annotations

import json
import math
import time
from typing import Any

from pydantic import ValidationError

from engtoolkit.core.registry import export_schema, get_tool


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if hasattr(obj, "item") and callable(obj.item):  # numpy scalars
        return _sanitize(obj.item())
    return obj


def _dumps(obj: Any) -> str:
    return json.dumps(_sanitize(obj), allow_nan=False)


def schema_json() -> str:
    return _dumps(export_schema())


def run_tool_json(tool_id: str, inputs_json: str = "{}") -> str:
    """Run a tool. Returns {"ok": true, "result": {...}, "charts": [...]} or {"ok": false, "error": {...}}."""
    t0 = time.perf_counter()
    try:
        tool = get_tool(tool_id)
    except KeyError as err:
        return _dumps({"ok": False, "error": {"kind": "unknown_tool", "message": str(err)}})
    try:
        inputs = tool.parse(json.loads(inputs_json or "{}"))
    except ValidationError as err:
        fields = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in err.errors()]
        return _dumps({"ok": False, "error": {"kind": "validation", "message": "Check the highlighted inputs",
                                              "fields": fields}})
    try:
        result = tool.func(inputs)
    except Exception as err:  # calculation errors are shown to the user, not raised into JavaScript
        return _dumps({"ok": False, "error": {"kind": "calculation", "message": str(err)}})
    charts, chart_error = [], None
    try:
        charts = [c.to_dict() for c in tool.make_charts(inputs, result)]
    except Exception as err:  # a failed chart should not hide the result
        chart_error = str(err)
    return _dumps({
        "ok": True, "tool": tool_id, "inputs": inputs.model_dump(mode="json"),
        "result": {"type": type(result).__name__, "fields": result.fields_info()},
        "charts": charts, "chart_error": chart_error,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    })


def choices_json() -> str:
    """Dropdown options for inputs with a ``choices`` hint (built ahead of time for the web app)."""
    from engtoolkit.catalogs import list_profiles
    from engtoolkit.materials import AIR, WATER, families, get_material, list_fluids, list_incompressibles, list_materials

    fast = [WATER, "INCOMP::MEG[0.3]", "INCOMP::MPG[0.3]", AIR]
    return _dumps({
        "fluids_fast": fast,
        "fluids": fast + [f for f in list_fluids()],
        "incompressibles": list_incompressibles(),
        "materials": {fam: list_materials(fam) for fam in families()},
        "material_info": {name: {"family": get_material(name).family, "source": get_material(name).source}
                          for name in list_materials()},
        "profiles": list_profiles(),
    })
