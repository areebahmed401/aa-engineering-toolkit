"""Thermofluids library checked against independent correlations and hand calculations."""
import math

import pytest
from CoolProp.CoolProp import PropsSI

from utils import CATALOG_DIR
from utils.Appendix.formulas import (
    colebrook_white, fully_turbulent_friction_factor, darcy_weisbach, get_Le_reducer,
)
from utils.Appendix.materials import get_material
from utils.Appendix.unit_convertors import Temperature, Pressure, Angle, rads_to_degrees
from utils.Appendix.thermofluids.pipe_flow import (
    Pipe, PipeFlow, PipeLine, PipeElement, CraneMinorLoss, PipeSizer,
    load_crane_data, load_pipe_catalog,
)
from utils.Appendix.thermofluids.pipe_weight_calc import SCHEDULE_40_DATA
from utils.Appendix.thermofluids.functions import (
    calc_insulation_thickness, insulated_pipe_heat_loss,
    cooling_tower_performance, cooling_tower_losses, get_refrigeration_cycle,
)

A106B = get_material("ASTM A106B")


def haaland(Re, eps_D):
    return (-1.8 * math.log10((eps_D / 3.7) ** 1.11 + 6.9 / Re)) ** -2


# ---------------- friction factor ----------------

@pytest.mark.parametrize("Re", [5e3, 1e5, 1e6])
@pytest.mark.parametrize("eps_D", [1e-5, 1e-3])
def test_colebrook_matches_haaland(Re, eps_D):
    D = 0.1
    assert colebrook_white(Re, eps_D * D, D) == pytest.approx(haaland(Re, eps_D), rel=0.02)


def test_laminar_friction_factor():
    assert colebrook_white(1000, 4.5e-5, 0.05) == pytest.approx(0.064)


def test_fully_turbulent_is_high_re_limit():
    D, eps = 0.1023, 4.5e-5
    assert fully_turbulent_friction_factor(eps, D) == pytest.approx(colebrook_white(1e9, eps, D), rel=1e-3)


def test_darcy_weisbach_head_si():
    # f = 0.02, 100 m of 0.1 m pipe at 2 m/s -> 4.08 m head
    assert darcy_weisbach(0.02, 100, 2.0, 0.1) == pytest.approx(0.02 * 1000 * 4 / (2 * 9.81))


def test_reducer_uses_area_ratio():
    assert get_Le_reducer(1, 0.1, 0.098) == pytest.approx(2.0 * 0.098)   # beta^2 > 0.9
    assert get_Le_reducer(1, 0.1, 0.05) == pytest.approx(38 * 0.05)      # beta^2 = 0.25


# ---------------- pipe flow ----------------

def test_pipe_pressure_drop_hand_calc():
    T, P = 293.15, 3e5
    D, length, Q = 0.05251, 100.0, 0.005
    flow = PipeFlow(Pipe(D, length, A106B), "Water", T, P)
    rho = PropsSI("D", "T", T, "P", P, "Water")
    mu = PropsSI("V", "T", T, "P", P, "Water")
    v = Q / (math.pi * D**2 / 4)
    f = haaland(rho * v * D / mu, A106B.roughness / D)
    assert flow.pressure_drop(Q) == pytest.approx(f * length / D * rho * v**2 / 2, rel=0.02)


def test_crane_fitting_uses_fully_turbulent_f():
    flow = PipeFlow(Pipe(0.10226, 50.0, A106B), "Water", 293.15, 3e5)
    crane = load_crane_data()
    elbow = CraneMinorLoss("elbow_90_standard", flow, crane)
    assert elbow.K == pytest.approx(fully_turbulent_friction_factor(A106B.roughness, 0.10226) * 30)
    line = PipeLine()
    line.add(PipeElement(flow))
    line.add(elbow)
    Q = 0.02
    assert line.total_pressure_drop(Q) == pytest.approx(flow.pressure_drop(Q) + elbow.pressure_drop(Q))


def test_unknown_fitting_raises():
    flow = PipeFlow(Pipe(0.1, 10.0, A106B), "Water", 293.15, 3e5)
    with pytest.raises(ValueError):
        CraneMinorLoss("not_a_fitting", flow, load_crane_data())


def test_pipe_catalog_uses_sch40_dimensions():
    catalog = load_pipe_catalog()
    for dn, (od_mm, t_mm) in SCHEDULE_40_DATA.items():
        if dn not in catalog:
            continue
        assert catalog[dn]["outer_D"] == pytest.approx(od_mm / 1000, abs=1e-5)
        assert catalog[dn]["inner_D"] == pytest.approx((od_mm - 2 * t_mm) / 1000, abs=1e-5)
    assert (CATALOG_DIR / "equivalent_lengths.csv").exists()


def test_size_for_max_dp_runs():
    sizer = PipeSizer("Water", A106B, 293.15, 3e5, length=100.0)
    D = sizer.size_for_max_dp(Q=0.005, dp_max=50e3, diameters=[0.04090, 0.05251, 0.06271, 0.07792])
    assert D in (0.05251, 0.06271, 0.07792)


# ---------------- insulation ----------------

def test_insulation_thickness_meets_heat_loss_target():
    args = dict(T_fluid_c=180, T_atm_c=25, k_ins=0.04)
    t_mm = calc_insulation_thickness(0.10226, 0.1143, q_max=50, **args)
    assert 0 < t_mm < 500
    q = insulated_pipe_heat_loss(0.10226, 0.1143, t_mm / 1000, **args)
    assert q == pytest.approx(50, rel=1e-6)


def test_insulation_not_needed_when_cold():
    assert calc_insulation_thickness(0.1, 0.11, T_fluid_c=20, T_atm_c=25, q_max=50, k_ins=0.04) == 0.0


# ---------------- cooling tower ----------------

def test_cooling_tower_energy_balance():
    m_dot, eff, dT, t_out = cooling_tower_performance(80, 4.18, 31, 18, 3)
    assert t_out == 21
    assert m_dot * 4.18 * dT == pytest.approx(80)
    assert eff == pytest.approx(10 / 13)


def test_cooling_tower_guards():
    with pytest.raises(ValueError):
        cooling_tower_performance(80, 4.18, 20, 18, 3)
    with pytest.raises(ValueError):
        cooling_tower_losses(1.0, 5.0, 1.0)


# ---------------- refrigeration cycle ----------------

def test_refrigeration_cycle_energy_balance():
    res = get_refrigeration_cycle("R134a", 0, 40, 10)
    COP, rdot, heat_load, cooling_load = res[22], res[23], res[24], res[25]
    assert heat_load == pytest.approx(cooling_load + 10)
    assert COP == pytest.approx(heat_load / 10)
    assert rdot > 0


def test_refrigeration_cycle_out_of_range_raises():
    with pytest.raises(ValueError):
        get_refrigeration_cycle("R134a", 0, 200, 10)  # above R134a critical temperature


# ---------------- unit converters ----------------

def test_unit_round_trips():
    assert Temperature.k_to_c(Temperature.c_to_k(25.0)) == pytest.approx(25.0)
    assert Temperature.f_to_c(212) == pytest.approx(100)
    assert Pressure.pa_to_bar(Pressure.bar_to_pa(5.0)) == pytest.approx(5.0)
    assert Angle.rad_to_deg(math.pi) == pytest.approx(180)
    assert rads_to_degrees(math.pi / 2) == pytest.approx(90)
