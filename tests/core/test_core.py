"""Registry, results, units, and the rule that every tool is validated."""
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import BaseModel

from engtoolkit.core import (
    Input, Result, convert, export_schema, from_si, get_tool, list_tools, register_tool, rfield, run, to_si,
)

TESTS_DIR = Path(__file__).resolve().parents[1]


def test_units_round_trip():
    assert to_si(5, "bar") == pytest.approx(5e5)
    assert to_si(25, "degC") == pytest.approx(298.15)
    assert from_si(298.15, "degF") == pytest.approx(77.0)
    assert from_si(2.5e6, "kJ/kg") == pytest.approx(2500)
    assert convert(1, "inch", "mm") == pytest.approx(25.4)


def test_result_helpers():
    @dataclass
    class Demo(Result):
        a: float = rfield("m", "Length")
        series: list = rfield("m", "Series", default_factory=list, summary=False)

    r = Demo(1.5, [1, 2])
    assert r.summary() == {"Length [m]": 1.5}
    assert r.to_dict() == {"a": 1.5, "series": [1, 2]}
    assert "Length [m]" in r._repr_markdown_()


def test_register_tool_requires_section_and_reference():
    class Inp(BaseModel):
        x: float = Input(1.0, "m", "X")

    with pytest.raises(ValueError):
        register_tool("nosection", "Bad", Inp, reference="ref")
    with pytest.raises(ValueError):
        register_tool("thermo.no_reference", "Bad", Inp)


def test_unknown_tool():
    with pytest.raises(KeyError):
        get_tool("thermo.does_not_exist")


# ---------------- rules every registered tool must follow ----------------

TOOLS = list_tools()


def test_tools_are_registered_for_each_built_section():
    sections = {t.section for t in TOOLS}
    assert {"thermo", "structural"} <= sections


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.id)
def test_tool_runs_with_defaults_and_serialises(tool):
    result = tool.run()
    assert isinstance(result, Result)
    json.dumps(result.to_dict())  # web worker sends results as JSON
    assert tool.reference


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.id)
def test_tool_inputs_have_labels(tool):
    props = tool.schema()["inputs"]["properties"]
    for name, spec in props.items():
        if "$ref" in spec or spec.get("type") == "array" or "allOf" in spec:
            continue  # nested models (sections, load lists) are labelled inside their own schema
        assert spec.get("label") or spec.get("description"), f"{tool.id}.{name} has no label"


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.id)
def test_every_tool_has_a_validation_test(tool):
    """A test named test_tool_<name> must exist in tests/<section>/."""
    name = tool.id.split(".", 1)[1]
    pattern = re.compile(rf"def test_tool_{re.escape(name)}\b")
    files = (TESTS_DIR / tool.section).glob("test_*.py")
    assert any(pattern.search(f.read_text(encoding="utf-8")) for f in files), \
        f"Add a validation test 'test_tool_{name}' in tests/{tool.section}/"


def test_export_schema_is_json():
    schema = export_schema()
    text = json.dumps(schema)
    assert schema["tools"] and "thermo.pipe_pressure_drop" in text
    spec = next(t for t in schema["tools"] if t["id"] == "thermo.pipe_pressure_drop")
    assert spec["inputs"]["properties"]["T"]["unit"] == "K"


def test_run_with_dict_and_kwargs():
    a = run("thermo.cooling_tower", {"heat_load": 50e3})
    b = run("thermo.cooling_tower", heat_load=50e3)
    assert a.water_flow == pytest.approx(b.water_flow)
    assert not math.isnan(a.water_flow)
