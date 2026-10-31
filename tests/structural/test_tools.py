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
