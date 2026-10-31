"""Friction factors and pipe flow against independent correlations and hand calculations."""
import math

import pytest

from engtoolkit.catalogs import crane_le_over_d, pipe
from engtoolkit.materials import fluid, get_material
from engtoolkit.thermo import (
    CraneMinorLoss, Pipe, PipeElement, PipeFlow, PipeLine, PipeSizer, colebrook_white, darcy_weisbach_dp,
    fully_turbulent_friction_factor, haaland, head_loss, pipe_pressure_drop, pipe_size_sweep, swamee_jain,
)

A106B = get_material("ASTM A106B")


@pytest.mark.parametrize("Re", [5e3, 1e5, 1e6])
@pytest.mark.parametrize("eps_D", [1e-5, 1e-3])
def test_colebrook_matches_explicit_correlations(Re, eps_D):
    D = 0.1
    f = colebrook_white(Re, eps_D * D, D)
    assert f == pytest.approx(haaland(Re, eps_D * D, D), rel=0.02)
    assert f == pytest.approx(swamee_jain(Re, eps_D * D, D), rel=0.02)


def test_laminar_friction_factor():
    assert colebrook_white(1000, 4.5e-5, 0.05) == pytest.approx(0.064)


def test_fully_turbulent_is_high_re_limit():
    D, eps = 0.10226, 4.5e-5
    assert fully_turbulent_friction_factor(eps, D) == pytest.approx(colebrook_white(1e9, eps, D), rel=1e-3)


def test_darcy_weisbach_si():
    assert head_loss(0.02, 100, 0.1, 2.0) == pytest.approx(0.02 * 1000 * 4 / (2 * 9.80665))
    assert darcy_weisbach_dp(0.02, 100, 0.1, 1000, 2.0) == pytest.approx(0.02 * 1000 * 0.5 * 1000 * 4)


def test_pipe_pressure_drop_hand_calc():
    T, P = 293.15, 3e5
    D, length, Q = 0.05251, 100.0, 0.005
    flow = PipeFlow(Pipe(D, length, A106B), "Water", T, P)
    s = fluid("Water").state(T=T, P=P)
    v = Q / (math.pi * D**2 / 4)
    f = haaland(s.rho * v * D / s.mu, A106B.roughness, D)
    assert flow.pressure_drop(Q) == pytest.approx(f * length / D * s.rho * v**2 / 2, rel=0.02)


def test_crane_fitting_uses_fully_turbulent_f():
    flow = PipeFlow(Pipe(0.10226, 50.0, A106B), "Water", 293.15, 3e5)
    elbow = CraneMinorLoss("elbow_90_standard", flow)
    assert elbow.K == pytest.approx(fully_turbulent_friction_factor(A106B.roughness, 0.10226) * 30)
    line = PipeLine()
    line.add(PipeElement(flow))
    line.add(elbow)
    Q = 0.02
    assert line.total_pressure_drop(Q) == pytest.approx(flow.pressure_drop(Q) + elbow.pressure_drop(Q))


def test_unknown_fitting_raises():
    flow = PipeFlow(Pipe(0.1, 10.0, A106B), "Water", 293.15, 3e5)
    with pytest.raises(ValueError):
        CraneMinorLoss("not_a_fitting", flow, crane_le_over_d())


def test_functional_pressure_drop_adds_elevation():
    size = pipe(50)
    base = pipe_pressure_drop("Water", 293.15, 3e5, size.id, 100, mass_flow=5.0)
    up = pipe_pressure_drop("Water", 293.15, 3e5, size.id, 100, mass_flow=5.0, elevation_change=10)
    assert up.dp_total - base.dp_total == pytest.approx(base.density * 9.80665 * 10)
    assert base.regime == "turbulent"


def test_size_sweep_and_sizer():
    rows = pipe_size_sweep("Water", 293.15, 3e5, 100, 5.0, dn_range=(40, 100))
    assert [r.dn for r in rows] == [40, 50, 65, 80, 90, 100]
    assert all(a.dp_total > b.dp_total for a, b in zip(rows, rows[1:]))  # bigger pipe, lower drop
    sizer = PipeSizer("Water", A106B, 293.15, 3e5, length=100.0)
    D = sizer.size_for_max_dp(Q=0.005, dp_max=50e3, diameters=[0.0409, 0.05251, 0.06271, 0.07792])
    assert D in (0.05251, 0.06271, 0.07792)
    assert sizer.size_for_max_velocity(0.01, 2.0) == pytest.approx(math.sqrt(4 * 0.01 / (math.pi * 2.0)))
