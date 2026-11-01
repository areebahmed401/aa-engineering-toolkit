"""Validation tests for the registered structural tools."""
import math

import pytest

from engtoolkit import run
from engtoolkit.materials import get_material


def test_tool_section_properties():
    r = run("structural.section_properties", shape="rectangle", width=0.1, height=0.2)
    assert r.Iyy == pytest.approx(0.1 * 0.2**3 / 12)
    assert r.W_el_y == pytest.approx(0.1 * 0.2**2 / 6)
    assert r.mass_per_m == pytest.approx(0.02 * 7850)


def test_tool_beam_analysis():
    # Cantilever, 10 kN at the tip of a 2 m span: M_max = PL, deflection = PL³/3EI
    r = run("structural.beam_analysis", {
        "section": {"shape": "rectangle", "width": 0.1, "height": 0.2},
        "length": 2.0, "left_support": "fixed", "right_support": "free",
        "loads": [{"kind": "point", "value": 10e3, "x": 2.0}],
    })
    EI = get_material("Steel").E * 0.1 * 0.2**3 / 12
    assert r.max_moment == pytest.approx(20e3, rel=1e-6)
    assert r.max_deflection == pytest.approx(10e3 * 8 / (3 * EI), rel=2e-3)
    assert r.Ay == pytest.approx(10e3)


def test_tool_beam_analysis_rejects_load_outside_span():
    with pytest.raises(ValueError):
        run("structural.beam_analysis", {"length": 2.0, "loads": [{"kind": "point", "value": 1e3, "x": 3.0}]})


def test_tool_torsion():
    # Closed section: Saint-Venant twist T L / (G J)
    r = run("structural.torsion", {"section": {"shape": "circle", "radius": 0.02}, "length": 1.0,
                                   "torque": 100.0, "position": 1.0})
    J = math.pi * 0.02**4 / 2
    assert r.twist == pytest.approx(100 / (get_material("Steel").G * J))
    # Open I-section: warping stiffens it, twist below Saint-Venant
    r2 = run("structural.torsion")
    assert r2.twist < r2.twist_saint_venant


DIMENSIONS = ("width", "height", "thickness", "web_thickness", "radius", "inner_radius", "profile")


@pytest.mark.parametrize("shape", ["rectangle", "square_tube", "rectangular_tube", "circle", "hollow_circle",
                                   "i_beam", "c_beam", "t_beam", "z_beam", "l_beam", "profile"])
def test_shape_fields_match_build_section(shape):
    # The web app shows only SHAPE_FIELDS[shape]: those inputs must change the section, the others must not
    from engtoolkit.structural.tools import SHAPE_FIELDS
    base = {"shape": shape, "width": 0.1, "height": 0.2, "thickness": 0.01, "web_thickness": 0.006,
            "radius": 0.05, "inner_radius": 0.04, "profile": "IPE 200"}
    ref = run("structural.section_properties", base)
    for name in DIMENSIONS:
        changed = {**base, name: "IPE 300" if name == "profile" else base[name] * 0.9}
        r = run("structural.section_properties", changed)
        assert (r.area != ref.area) == (name in SHAPE_FIELDS[shape]), name


def test_shape_fields_in_schema():
    from engtoolkit.core.registry import get_tool
    from engtoolkit.structural.tools import SHAPE_FIELDS, SHAPE_LABELS
    schema = get_tool("structural.section_properties").schema()["inputs"]
    shape = schema["properties"]["shape"]
    assert {k: dict(v) for k, v in shape["shape_fields"].items()} == SHAPE_FIELDS
    assert [name for name, _ in shape["shape_fields"]["i_beam"]] == list(SHAPE_FIELDS["i_beam"])
    assert set(shape["shape_labels"]) == set(SHAPE_FIELDS) == set(shape["enum"])


def test_section_designation():
    assert run("structural.section_properties", shape="profile", profile="IPE 200").designation == "IPE 200"
    assert run("structural.section_properties", shape="rectangle").designation == "Rectangle"


def test_beam_propped_cantilever_peaks():
    # Fixed-pinned, central P (Gere & Goodno table): R_A = 11P/16, R_B = 5P/16, M_A = 3PL/16 (governs),
    # M under the load = 5PL/32; max deflection PL³/(48√5 EI) at x = L/√5 from the pinned end
    P, L = 10e3, 2.0
    r = run("structural.beam_analysis", {
        "section": {"shape": "rectangle", "width": 0.1, "height": 0.2},
        "length": L, "left_support": "fixed", "right_support": "pinned",
        "loads": [{"kind": "point", "value": P, "x": L / 2}],
    })
    EI = get_material("Steel").E * 0.1 * 0.2**3 / 12
    assert r.degree_of_indeterminacy == 1
    assert r.Ay == pytest.approx(11 * P / 16, rel=1e-3)
    assert r.By == pytest.approx(5 * P / 16, rel=1e-3)
    assert r.max_moment == pytest.approx(3 * P * L / 16, rel=1e-3)
    assert r.x_max_moment == pytest.approx(0.0, abs=L / 100)
    assert r.max_deflection == pytest.approx(P * L**3 / (48 * math.sqrt(5) * EI), rel=2e-3)
    assert r.x_max_deflection == pytest.approx(L - L / math.sqrt(5), abs=L / 100)
    assert r.max_bending_stress == pytest.approx(r.max_moment * 0.1 / (0.1 * 0.2**3 / 12))
    assert r.utilisation == pytest.approx(r.max_bending_stress / r.yield_strength)
    assert r.section == "Rectangle"
