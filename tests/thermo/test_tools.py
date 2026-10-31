"""Validation tests for the registered thermo tools."""
import pytest

from engtoolkit import run
from engtoolkit.catalogs import pipe


def test_tool_fluid_properties():
    # IAPWS-95 saturated vapour at 100 °C: h_g = 2675.6 kJ/kg (Cengel Table A-4)
    r = run("thermo.fluid_properties", fluid="Water", input_1="T", value_1=373.15, input_2="Q", value_2=1.0)
    assert r.h == pytest.approx(2675.6e3, rel=1e-3)
    with pytest.raises(ValueError):
        run("thermo.fluid_properties", input_1="T", input_2="T")


def test_tool_saturated_steam_table():
    r = run("thermo.saturated_steam_table", by="pressure", start=1e5, stop=10e5, points=4)
    assert r.n_rows == 4
    assert r.columns[0] == "T [°C]"
    assert r.rows[0][0] == pytest.approx(99.61, abs=0.05)  # Tsat at 1 bar


def test_tool_pipe_pressure_drop():
    base = run("thermo.pipe_pressure_drop")
    with_fittings = run("thermo.pipe_pressure_drop", n_elbow_90=4)
    assert base.inner_diameter == pytest.approx(pipe(50).id)
    assert base.dp_fittings == 0
    assert with_fittings.dp_total > base.dp_total
    assert base.velocity == pytest.approx(5.0 / base.density / pipe(50).flow_area)


def test_tool_insulation_thickness():
    r = run("thermo.insulation_thickness", q_max=50)
    assert r.heat_loss == pytest.approx(50, rel=1e-6)


def test_tool_insulation_heat_loss():
    thin = run("thermo.insulation_heat_loss", thickness=0.02)
    thick = run("thermo.insulation_heat_loss", thickness=0.1)
    assert thick.heat_loss < thin.heat_loss < thin.bare_heat_loss
    assert thick.T_surface < thin.T_surface


def test_tool_refrigeration_cycle():
    r = run("thermo.refrigeration_cycle")
    assert r.heating_load == pytest.approx(r.cooling_load + r.compressor_power)
    assert len(r.states) == 4


def test_tool_cooling_tower():
    r = run("thermo.cooling_tower")
    assert r.water_flow * 4186 * r.range == pytest.approx(80e3)
