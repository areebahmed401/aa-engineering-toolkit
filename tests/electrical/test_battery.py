"""Battery models: equivalent circuit, thermal coupling, aging correlations and the cell catalog."""
import math

import numpy as np
import pytest

from engtoolkit.catalogs import get_cell, list_cells
from engtoolkit.electrical.battery import Cooling, ECMParams, ThermalModel, simulate
from engtoolkit.electrical.battery import aging
from engtoolkit.materials import AIR, fluid
from engtoolkit.thermo import heat_transfer as ht

FLAT = dict(soc=(0.0, 1.0), ocv=(3.7, 3.7), V_min=0.0, V_max=5.0)


def flat_cell(R0=0.01, R1=0.02, tau1=10.0, R2=0.03, tau2=100.0, Q=5.0):
    return ECMParams(Q, R0=R0, R1=R1, tau1=tau1, R2=R2, tau2=tau2, **FLAT)


# ---------------- catalog ----------------

@pytest.mark.parametrize("name", list_cells())
def test_cell_catalog_is_consistent(name):
    c = get_cell(name)
    assert c.source and c.aging_model in aging.MODELS
    assert c.V_min < c.V_nominal < c.V_max
    assert c.ocv[0] == pytest.approx(c.V_min, abs=0.05) and c.V_nominal < c.ocv[-1] <= c.V_max
    assert np.all(np.diff(c.ocv) > 0) and np.all(np.diff(c.soc) > 0)
    assert 80 < c.specific_energy < 320  # W·h/kg, commercial Li-ion range
    assert c.surface_area > 0 and c.C1 == pytest.approx(c.tau1 / c.R1)


def test_m50_surface_area_and_energy():
    c = get_cell("LG M50 21700 (NMC811)")
    assert c.surface_area == pytest.approx(math.pi * 0.0211 * 0.0703 + math.pi * 0.0211**2 / 2)
    assert c.energy_Wh == pytest.approx(18.15)


# ---------------- equivalent circuit ----------------

@pytest.mark.parametrize("n_rc", [1, 2])
def test_rc_step_response_is_analytical(n_rc):
    """Constant current step: V(t) = OCV - I·R0 - I·R1·(1 - e^(-t/τ1)) - I·R2·(1 - e^(-t/τ2)) exactly."""
    p = flat_cell(R2=0.03 if n_rc == 2 else 0.0)
    I = 5.0
    sim = simulate(p, current_fn=lambda t: I, dt=1.0, t_max=600, soc0=1.0)
    t = sim.t
    expected = 3.7 - I * (p.R0 + p.R1 * (1 - np.exp(-t / p.tau1)) + p.R2 * (1 - np.exp(-t / p.tau2)))
    np.testing.assert_allclose(sim.voltage, expected, atol=1e-12)


def test_coulomb_counting_delivers_rated_capacity():
    p = flat_cell()
    sim = simulate(p, "discharge_cc", c_rate=1.0, dt=1.0)
    assert sim.stop_reason == "SOC reached 0"
    assert sim.capacity_Ah == pytest.approx(5.0, abs=5.0 / 3600 * 2)
    np.testing.assert_allclose(sim.soc, 1 - sim.t / 3600, atol=1e-12)


def test_electrical_energy_balance():
    """Chemical energy ∫I·OCV = delivered ∫I·V + losses ∫(I²R0 + V1²/R1 + V2²/R2) + capacitor energy."""
    cell = get_cell("LG M50 21700 (NMC811)")
    p = ECMParams.from_cell(cell)
    sim = simulate(p, "discharge_cc", c_rate=1.0, dt=1.0)
    chem = np.sum(sim.current * p.ocv_at(sim.soc)) * 1.0
    delivered = np.sum(sim.current * sim.voltage) * 1.0
    losses = np.sum(sim.heat - (-sim.current * sim.temperature * p.dUdT_at(sim.soc))) * 1.0
    assert chem == pytest.approx(delivered + losses, rel=2e-3)


def test_constant_power_holds_power():
    cell = get_cell("LG M50 21700 (NMC811)")
    sim = simulate(ECMParams.from_cell(cell), "discharge_cp", power=15.0)
    np.testing.assert_allclose(sim.power, 15.0, rtol=1e-9)
    assert sim.stop_reason == "lower cut-off voltage"


def test_cccv_charge_respects_voltage_limit():
    cell = get_cell("LG M50 21700 (NMC811)")
    sim = simulate(ECMParams.from_cell(cell), "charge_cccv", c_rate=0.5)
    assert sim.voltage.max() <= cell.V_max + 1e-9
    assert sim.stop_reason.startswith("charge complete")
    assert sim.soc[-1] > 0.95 and -sim.current[-1] < 0.06 * cell.capacity_Ah


def test_drive_cycle_limits_regen_and_ends_at_cutoff():
    cell = get_cell("A123 ANR26650M1B (LFP)")
    sim = simulate(ECMParams.from_cell(cell), "drive_cycle", c_rate=3.0)
    assert sim.current.min() < 0 and sim.voltage.max() <= cell.V_max + 1e-9
    assert sim.stop_reason in ("lower cut-off voltage", "SOC reached 0")


def test_arrhenius_resistance():
    p = ECMParams.from_cell(get_cell("LG M50 21700 (NMC811)"))
    assert p.resistance_factor(p.T_ref) == 1.0
    assert p.resistance_factor(273.15) == pytest.approx(math.exp(p.Ea_R / 8.314462618 * (1 / 273.15 - 1 / 298.15)))


# ---------------- thermal ----------------

def test_thermal_step_matches_analytical_first_order_response():
    cell = get_cell("LG M50 21700 (NMC811)")
    th = ThermalModel.for_cell(cell, Cooling("fixed_h", T_coolant=300.0, h_fixed=20.0))
    hA, mc, Q = 20.0 * cell.surface_area, cell.mass * cell.cp, 2.0
    T, ts = 300.0, np.arange(1, 2001)
    temps = []
    for _ in ts:
        T = th.step(T, Q, 1.0)
        temps.append(T)
    expected = 300.0 + Q / hA * (1 - np.exp(-ts * hA / mc))
    np.testing.assert_allclose(temps, expected, rtol=1e-12)
    assert th.steady_state(Q) == pytest.approx(300.0 + Q / hA)


@pytest.mark.parametrize("kind", ["natural_air", "forced_air", "liquid_cold_plate", "adiabatic"])
def test_thermal_energy_balance(kind):
    """m·cp·ΔT = ∫Q_gen dt - ∫Q_removed dt over a coupled discharge."""
    cell = get_cell("LG M50 21700 (NMC811)")
    sim = simulate(ECMParams.from_cell(cell), "discharge_cc", c_rate=1.5, dt=1.0, T0=298.15,
                   thermal=ThermalModel.for_cell(cell, Cooling(kind)))
    stored = cell.mass * cell.cp * (sim.temperature[-1] - sim.temperature[0])
    net = np.sum(sim.heat[:-1] - sim.heat_removed[:-1]) * 1.0
    assert stored == pytest.approx(net, rel=0.02)
    if kind == "adiabatic":
        assert np.all(sim.heat_removed == 0)


def test_cooling_uses_thermo_correlations_and_fluid_properties():
    cell = get_cell("LG M50 21700 (NMC811)")
    forced = ThermalModel.for_cell(cell, Cooling("forced_air", T_coolant=298.15, air_velocity=3.0))
    assert forced.info["h_forced"] == pytest.approx(ht.forced_convection_cylinder(3.0, 303.15, 298.15, 0.0211, AIR))
    c = Cooling("liquid_cold_plate", T_coolant=298.15, coolant_velocity=0.5, channel_diameter=0.006)
    liquid = ThermalModel.for_cell(cell, c)
    s = fluid("INCOMP::MEG[0.3]").state(T=298.15, P=2e5)
    Re = s.rho * 0.5 * 0.006 / s.mu
    assert liquid.info["Re_channel"] == pytest.approx(Re)
    assert liquid.info["h_channel"] == pytest.approx(ht.nusselt_internal(Re, s.Pr, "constant_q") * s.k / 0.006)
    nat = ThermalModel.for_cell(cell, Cooling("natural_air"))
    hA = nat.conductance(320.0)[0]
    expected = (ht.natural_convection_horizontal_cylinder(320.0, 298.15, 0.0211) +
                ht.h_radiation(0.8, 320.0, 298.15)) * cell.surface_area
    assert hA == pytest.approx(expected)


def test_flat_plate_correlation_laminar_textbook_value():
    """Incropera eq. 7.30: Nu = 0.664·Re^0.5·Pr^(1/3) (air 300 K, 2 m/s, 0.3 m)."""
    s = fluid(AIR).state(T=300.0)
    Re = s.rho * 2.0 * 0.3 / s.mu
    h = ht.forced_convection_flat_plate(2.0, 300.0, 300.0, 0.3)
    assert h == pytest.approx(0.664 * Re**0.5 * s.Pr ** (1 / 3) * s.k / 0.3)
    assert 5 < h < 15


# ---------------- aging ----------------

@pytest.mark.parametrize("T", [273.15, 298.15, 318.15, 333.15])
@pytest.mark.parametrize("ah", [100.0, 1000.0, 10000.0])
def test_wang2011_rate_model_reproduces_single_rate_fit_at_c2(T, ah):
    """The C-rate-dependent model at C/2 agrees with the paper's own C/2 fit within a few percent."""
    multi = aging.wang2011_capacity_loss(ah, 0.5, T)
    single = aging.wang2011_capacity_loss_c2(ah, T)
    assert multi == pytest.approx(single, rel=0.05)


def test_wang2011_tabulated_B_and_trends():
    for c, b in zip(aging.WANG_C_RATES, aging.WANG_B):
        assert aging.wang2011_B(c) == b
    # higher temperature ages faster; at fixed Ah the activation energy falls with C-rate
    assert aging.wang2011_capacity_loss(1000, 0.5, 333.15) > aging.wang2011_capacity_loss(1000, 0.5, 298.15)
    assert aging.wang2011_capacity_loss(1000, 10, 298.15) > aging.wang2011_capacity_loss(1000, 0.5, 298.15)


def test_schmalstieg2014_coefficients():
    """Calendar/cycle factors from the paper's fitted equations (hand-calculated values)."""
    assert aging.schmalstieg2014_alpha_cap(4.0, 323.15) == pytest.approx((7.543 * 4 - 23.75) * 1e6 * math.exp(-6976 / 323.15))
    assert aging.schmalstieg2014_alpha_cap(4.0, 323.15) == pytest.approx(2.70e-3, rel=0.01)
    assert aging.schmalstieg2014_beta_cap(3.667, 0.0) == pytest.approx(7.6e-4)
    assert aging.schmalstieg2014_beta_res(3.725, 1.0) == pytest.approx(2.798e-4 - 1.521e-5)
    cap, res = aging.schmalstieg2014_calendar(300, 4.0, 323.15)
    assert cap == pytest.approx(1 - 2.70e-3 * 300**0.75, rel=1e-3)
    # storage at lower voltage and temperature ages less
    assert aging.schmalstieg2014_calendar(300, 3.6, 298.15)[0] > cap and res > 1


def test_cycle_aging_curve():
    curve = aging.cycle_aging("schmalstieg2014_nmc", np.linspace(0, 3000, 301), c_rate=1, T=298.15, V_mean=3.7)
    assert curve.capacity[0] == 1.0 and np.all(np.diff(curve.capacity) <= 0)
    n80 = curve.cycles_to(0.8)
    assert np.interp(n80, curve.cycles, curve.capacity) == pytest.approx(0.8, abs=1e-3)
    shallow = aging.cycle_aging("schmalstieg2014_nmc", curve.cycles, c_rate=1, T=298.15, V_mean=3.7, dod=0.5)
    assert shallow.cycles_to(0.8) > n80  # in full-equivalent cycles, shallow cycling lasts longer
    lfp = aging.cycle_aging("wang2011_lfp", curve.cycles, c_rate=1, T=298.15)
    assert np.all(np.isnan(lfp.resistance))
    with pytest.raises(KeyError):
        aging.cycle_aging("unknown", [0, 1])
