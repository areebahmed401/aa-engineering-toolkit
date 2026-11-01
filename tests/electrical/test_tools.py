"""Validation tests for the electrical tools (one test_tool_<name> per registered tool)."""
import json
import math

import numpy as np
import pytest

from engtoolkit import run
from engtoolkit.catalogs import get_cell
from engtoolkit.electrical.battery import Cooling, ECMParams, ThermalModel, reference, simulate
from engtoolkit.electrical.tools import parse_rates
from engtoolkit.webapi import run_tool_json


def test_tool_battery_simulator():
    """Coulomb counting against the integrated current, energy balance, and the PyBaMM overlay."""
    res = run("electrical.battery_simulator", c_rates="0.5, 1, 2", cooling="natural_air")
    assert res.cell == "LG M50 21700 (NMC811)"
    # full discharge at 1C or below delivers close to the rated 5 Ah
    assert len(res.rows) == 3 and all(4.8 < row[1] <= 5.05 for row in res.rows[:2])
    assert res.stop_reason == "lower cut-off voltage"
    assert res.rows[0][4] < res.rows[1][4] < res.rows[2][4]  # higher rate, hotter cell
    assert res.energy == pytest.approx(res.capacity * 3.68, rel=0.03)  # mean discharge voltage ~3.7 V
    ids = [c.id for c in res.chart_specs]
    assert ids == ["voltage", "temperature", "soc", "heat", "capacity_fade"]
    assert any(s.name.startswith("PyBaMM") and s.dash for s in res.chart_specs[0].series)
    # pack scaling
    pack = run("electrical.battery_simulator", n_series=96, n_parallel=4, aging_cycles=0, compare_pybamm=False)
    cell = get_cell(pack.cell)
    assert pack.pack_voltage == pytest.approx(96 * cell.V_nominal)
    assert pack.pack_energy == pytest.approx(384 * cell.energy_Wh)
    assert [c.id for c in pack.chart_specs] == ["voltage", "temperature", "soc", "heat"]


@pytest.mark.parametrize("mode", ["discharge_cp", "drive_cycle", "charge_cccv"])
def test_battery_simulator_profiles(mode):
    out = json.loads(run_tool_json("electrical.battery_simulator", json.dumps({"mode": mode, "c_rates": "1"})))
    assert out["ok"], out
    assert out["charts"]


def test_rates_are_validated():
    assert parse_rates("0.5; 1, 2") == [0.5, 1.0, 2.0]
    for bad in ("", "a", "0", "1,2,3,4,5,6"):
        with pytest.raises(ValueError):
            parse_rates(bad)
    out = json.loads(run_tool_json("electrical.battery_simulator", json.dumps({"c_rates": "x"})))
    assert not out["ok"] and out["error"]["kind"] == "validation"


def test_tool_cooling_comparison():
    """Peak temperatures order with cooling strength; adiabatic rise = ∫Q dt / (m·cp); steady state check."""
    res = run("electrical.cooling_comparison", c_rate=1.5)
    assert res.T_max_liquid < res.T_max_forced < res.T_max_natural < res.T_max_adiabatic
    assert res.best == "Liquid cold plate"
    cell = get_cell("LG M50 21700 (NMC811)")
    adiabatic = next(r for r in res.rows if r[0].startswith("Adiabatic"))
    assert adiabatic[3] == pytest.approx(adiabatic[4] * 1e3 / (cell.mass * cell.cp), rel=0.02)
    assert 1000 < res.Re_channel < 2300 and res.h_channel > res.h_forced > 10
    # a long constant-current hold settles at the lumped steady state Q = h·A·(T - T_coolant)
    th = ThermalModel.for_cell(cell, Cooling("forced_air"))
    p = ECMParams.from_cell(cell)
    sim = simulate(p, current_fn=lambda t: 5.0 if (t // 600) % 2 == 0 else -5.0, dt=1.0, t_max=6 * 3600,
                   soc0=0.5, thermal=th)
    q_mean = np.mean(sim.heat[-3600:])
    assert np.mean(sim.temperature[-3600:]) == pytest.approx(th.steady_state(q_mean), abs=0.3)


def test_tool_cycle_life():
    """Reproduces the Schmalstieg (NMC) and Wang (LFP) correlations at the tool's operating points."""
    from engtoolkit.electrical.battery import aging
    res = run("electrical.cycle_life", c_rates="1", n_cycles=1000, use_thermal=False)
    cell = get_cell("LG M50 21700 (NMC811)")
    V = float(np.mean(cell.ocv_at(np.linspace(0, 1, 50))))
    days = 1000 * (1 / 1 + 1 / 0.5) / 24
    cap, r = aging.schmalstieg2014(days, 2 * 1000 * 2.05, V, 1.0, 298.15)
    assert res.capacity_end == pytest.approx(float(cap), rel=1e-6)
    assert res.resistance_end == pytest.approx(float(r), rel=1e-6)
    lfp = run("electrical.cycle_life", cell="A123 ANR26650M1B (LFP)", c_rates="0.5, 2", n_cycles=3000,
              T_ambient=318.15, use_thermal=False)
    loss = aging.wang2011_capacity_loss(3000 * 2.2, 0.5, 318.15)
    assert lfp.rows[0][3] == pytest.approx(1 - loss / 100, abs=1e-4)
    assert math.isnan(lfp.resistance_end)
    # with the thermal model a hotter (higher-rate) cycle runs above ambient
    hot = run("electrical.cycle_life", c_rates="2", cooling="natural_air")
    assert hot.T_cycle > 298.15


def test_tool_pybamm_reference():
    """The committed PyBaMM grid is complete, and the ECM fitted to the DFN agrees with it at 25 °C."""
    data = reference.load()
    assert data["meta"]["cell"] == "LG M50 21700 (NMC811)"
    assert reference.c_rates() == [0.5, 1.0, 2.0] and len(reference.temperatures()) == 3
    for r in data["discharge"]:
        assert r["voltage"][-1] == pytest.approx(2.5, abs=0.02) and np.all(np.diff(r["capacity_Ah"]) >= 0)
    for a in data["aging"]:
        assert a["capacity"][0] == 1.0 and 0.9 < a["capacity"][-1] < 1.0
    res = run("electrical.pybamm_reference", T_ambient=298.15)
    assert res.max_capacity_error < 0.04
    for row in res.rows:  # end-of-discharge temperature within 4 K of the DFN
        assert row[4] == pytest.approx(row[3], abs=4.0)
    fit = data["ecm_fit"]["fits"][1]
    cell = get_cell(res.cell)
    assert cell.R0 == pytest.approx(fit["R0"], rel=0.01) and cell.R2 == pytest.approx(fit["R2"], rel=0.01)
