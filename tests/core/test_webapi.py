"""JSON interface used by the web app worker."""
import json

import pytest

from engtoolkit.core import list_tools
from engtoolkit.webapi import choices_json, run_tool_json, schema_json


@pytest.mark.parametrize("tool", list_tools(), ids=lambda t: t.id)
def test_every_tool_runs_through_the_json_api(tool):
    out = json.loads(run_tool_json(tool.id, "{}"))
    assert out["ok"], out.get("error")
    assert out["result"]["fields"]
    if tool.charts is not None and tool.id != "thermo.cooling_tower":
        assert out["charts"] and out["chart_error"] is None


def test_validation_errors_point_at_fields():
    out = json.loads(run_tool_json("thermo.cooling_tower", json.dumps({"RH": 2.0})))
    assert not out["ok"] and out["error"]["kind"] == "validation"
    assert out["error"]["fields"][0]["loc"] == ["RH"]


def test_calculation_errors_are_reported_not_raised():
    out = json.loads(run_tool_json("thermo.cooling_tower", json.dumps({"T_hot_water": 280.0})))
    assert not out["ok"] and out["error"]["kind"] == "calculation"


def test_nan_becomes_null_and_unknown_tool():
    out = json.loads(run_tool_json("structural.beam_analysis", "{}"))
    fields = {f["name"]: f["value"] for f in out["result"]["fields"]}
    assert fields["By"] is None  # cantilever: no right reaction
    assert json.loads(run_tool_json("thermo.nope"))["error"]["kind"] == "unknown_tool"


def test_schema_and_choices():
    schema = json.loads(schema_json())
    assert any(t["has_charts"] for t in schema["tools"])
    choices = json.loads(choices_json())
    assert choices["fluids"][0] == "IF97::Water"
    assert "Mineral wool" in choices["materials"]["insulation"]
    assert "IPE 200" in choices["profiles"]
