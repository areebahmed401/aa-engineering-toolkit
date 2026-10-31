"""Materials library, temperature curves, fluids and catalogs."""
import math

import pytest

from engtoolkit.catalogs import crane_le_over_d, fitting_cost, get_profile, list_profiles, pipe, pipes, valve_cost
from engtoolkit.materials import (
    Material, add_material, families, fluid, get_material, list_fluids, list_materials, load_materials,
)


def test_lookup_by_name_alias_and_case():
    assert get_material("carbon steel") is get_material("ASTM A106B")
    assert get_material("Stainless Steel").name == "SS304"
    with pytest.raises(KeyError):
        get_material("unobtainium")


def test_every_material_has_a_source_and_known_family():
    for name in list_materials():
        m = get_material(name)
        assert m.source, f"{name} has no source"
    assert {"metal", "insulation", "polymer"} <= set(families())


def test_shear_modulus_derived():
    s = get_material("Steel")
    assert s.G == pytest.approx(200e9 / 2.6)


def test_temperature_curve_interpolates_and_clamps():
    m = get_material("Mineral wool")
    assert m.is_temperature_dependent("k")
    assert m.prop("k", 273.15 + 75) == pytest.approx((0.039 + 0.044) / 2)
    assert m.prop("k", 273.15 - 50) == pytest.approx(0.035)  # clamped at the first point
    assert m.k == pytest.approx(m.prop("k", 293.15))


def test_add_and_load_user_materials():
    add_material("Test alloy", "metal", mechanical={"E": "205e9", "nu": 0.29, "rho": 7900},
                 thermal={"k": {"T_C": [20, 200], "value": [40, 36]}}, replace=True)
    m = get_material("test alloy")
    assert m.E == 205e9 and m.prop("k", 293.15 + 90) == pytest.approx(38)
    loaded = load_materials("materials:\n  - name: Foam X\n    family: insulation\n    source: test\n"
                            "    thermal: {k: 0.03}\n")
    assert loaded[0].k == 0.03
    with pytest.raises(ValueError):
        Material.from_dict({"name": "Bad", "mechanical": {"stiffness": 1}})


def test_material_table_lists_properties_with_units():
    rows = get_material("SS304").table()
    k_row = next(r for r in rows if r["property"] == "k")
    assert k_row["unit"] == "W/(m·K)" and k_row["temperature_dependent"]


# ---------------- fluids ----------------

def test_water_density_at_25c():
    assert fluid("Water").state(T=298.15, P=101325).rho == pytest.approx(997.05, rel=1e-4)


def test_fluid_state_requires_two_inputs():
    with pytest.raises(ValueError):
        fluid("Water").state(T=300)
    with pytest.raises(ValueError):
        fluid("Water").state(T=300, X=1)


def test_saturation_and_constants():
    liq, vap = fluid("Water").saturation(P=101325)
    assert liq.T == pytest.approx(373.124, abs=0.01)
    assert vap.Q == 1.0 and liq.Q == 0.0
    assert fluid("Water").T_critical == pytest.approx(647.096, rel=1e-5)
    assert "R134a" in list_fluids()


def test_incompressible_coolant():
    s = fluid("INCOMP::MEG[0.3]").state(T=300, P=2e5)
    assert s.phase == "liquid"
    assert 1000 < s.rho < 1100
    assert math.isnan(s.Q)


# ---------------- catalogs ----------------

def test_pipe_sizes_are_od_minus_two_walls():
    p = pipe(100, "40")
    assert p.od == pytest.approx(0.1143) and p.wall == pytest.approx(0.00602)
    assert p.id == pytest.approx(0.1143 - 2 * 0.00602)
    assert pipe(100, "80").id < p.id < pipe(100, "10").id
    assert pipes.schedules() == ["10", "40", "80"]
    assert p.mass_per_m() == pytest.approx(16.07, rel=0.01)  # B36.10 DN100 Sch 40: 16.07 kg/m


def test_catalog_costs_and_fittings():
    assert pipes.cost_per_m(50) == 6.31
    assert crane_le_over_d()["elbow_90_standard"] == 30
    assert fitting_cost("elbow_90_LR", 100) == 14.46
    assert valve_cost(100, "CS", "electric") == 445.62


def test_profiles():
    p = get_profile("ipe200")
    assert p.h == 0.2 and p.web_height == pytest.approx(0.2 - 2 * 0.0085)
    assert "IPE 300" in list_profiles("IPE")
