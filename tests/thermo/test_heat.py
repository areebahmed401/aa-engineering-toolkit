"""Heat transfer, insulation, steam tables, cycles, psychrometrics, cooling tower and vacuum."""
import math

import pytest

from engtoolkit.thermo import (
    atmospheric_pressure, continuous_load, cooling_tower, dittus_boelter, gnielinski, h_radiation,
    insulated_pipe_heat_loss, insulation_thickness, lmtd, moist_air_state, natural_convection_horizontal_cylinder,
    nusselt_internal, pumpdown, refrigerant_info, refrigeration_cycle, saturated_table, steam_state,
    superheated_table,
)

# ---------------- correlations ----------------

def test_gnielinski_close_to_dittus_boelter_in_turbulent_range():
    assert gnielinski(1e5, 0.7) == pytest.approx(dittus_boelter(1e5, 0.7), rel=0.15)


def test_internal_nusselt_regimes():
    assert nusselt_internal(1000, 5) == 3.66
    assert nusselt_internal(1000, 5, boundary="constant_q") == 4.36
    assert nusselt_internal(5e4, 5) == pytest.approx(gnielinski(5e4, 5))


def test_natural_convection_incropera_example_9_3():
    # Incropera Ex. 9.3: 0.1 m pipe at 165 °C in 23 °C still air: Nu_D = 23.3, h = 7.30 W/m²K
    h = natural_convection_horizontal_cylinder(438.15, 296.15, 0.1)
    assert h == pytest.approx(7.30, rel=0.03)


def test_radiation_coefficient():
    assert h_radiation(1.0, 300.0, 300.0) == pytest.approx(4 * 5.670374419e-8 * 300**3)


def test_lmtd():
    assert lmtd(100, 60, 20, 40) == pytest.approx((60 - 40) / math.log(60 / 40))
    with pytest.raises(ValueError):
        lmtd(50, 40, 45, 60)


# ---------------- insulation ----------------

def test_insulated_pipe_fixed_h_matches_series_resistances():
    d_in, d_out, t, k, h = 0.10226, 0.1143, 0.05, 0.04, 10.0
    r = insulated_pipe_heat_loss(d_in, d_out, t, 453.15, 298.15, k, h_outer=h)
    from engtoolkit.materials import get_material
    k_pipe = get_material("Carbon Steel").prop("k", 453.15)
    R = (math.log(d_out / d_in) / (2 * math.pi * k_pipe) + math.log((d_out + 2 * t) / d_out) / (2 * math.pi * k)
         + 1 / (h * math.pi * (d_out + 2 * t)))
    assert r.heat_loss == pytest.approx(155 / R, rel=1e-6)
    assert r.bare_heat_loss > r.heat_loss


def test_insulation_thickness_meets_target_with_material_k():
    r = insulation_thickness(0.10226, 0.1143, 453.15, 298.15, q_max=50, k_insulation="Mineral wool")
    assert 0 < r.thickness < 0.5
    assert r.heat_loss == pytest.approx(50, rel=1e-6)
    # conductivity evaluated at the mean insulation temperature, above its 10 °C value
    assert r.k_insulation > 0.035


def test_insulation_not_needed_when_cold():
    r = insulation_thickness(0.1, 0.11, 293.15, 298.15, q_max=50, k_insulation=0.04)
    assert r.thickness == 0.0


def test_insulation_target_unreachable_raises():
    with pytest.raises(ValueError):
        insulation_thickness(0.1, 0.11, 900, 298.15, q_max=1, k_insulation=0.1, t_max=0.05)


# ---------------- steam tables ----------------

def test_saturated_table_matches_cengel_table_a4():
    # Cengel & Boles Table A-4 at 100 °C: P = 101.42 kPa, hf = 419.17, hfg = 2256.4, hg = 2675.6 kJ/kg
    row = saturated_table(T=[373.15]).iloc[0]
    assert row["P [kPa]"] == pytest.approx(101.42, rel=1e-3)
    assert row["h_f [kJ/kg]"] == pytest.approx(419.17, rel=1e-3)
    assert row["h_fg [kJ/kg]"] == pytest.approx(2256.4, rel=1e-3)
    assert row["h_g [kJ/kg]"] == pytest.approx(2675.6, rel=1e-3)
    assert row["v_g [m³/kg]"] == pytest.approx(1.6720, rel=1e-3)


def test_if97_close_to_iapws95():
    a = steam_state(T=473.15, P=10e5)
    b = steam_state("IF97", T=473.15, P=10e5)
    assert a.h == pytest.approx(b.h, rel=1e-4)


def test_superheated_table():
    df = superheated_table(1e6, [473.15, 573.15])  # 1 MPa, 200 and 300 °C (Cengel A-6: 2828.3, 3051.6)
    assert list(df["h [kJ/kg]"].round(0)) == pytest.approx([2828.0, 3051.0], abs=2)


# ---------------- refrigeration cycle ----------------

def test_refrigeration_cycle_energy_balance_and_efficiency():
    r = refrigeration_cycle("R134a", 273.15, 313.15, 10e3, isentropic_efficiency=0.75)
    assert r.heating_load == pytest.approx(r.cooling_load + 10e3)
    assert r.COP_heating == pytest.approx(r.COP_cooling + 1)
    ideal = refrigeration_cycle("R134a", 273.15, 313.15, 10e3, isentropic_efficiency=1.0)
    assert ideal.COP_cooling > r.COP_cooling
    assert r.COP_cooling < 273.15 / 40  # below Carnot


def test_refrigeration_cycle_state_labels():
    r = refrigeration_cycle("R134a", 273.15, 313.15, 10e3)
    labels = [st.state for st in r.states]
    assert labels[:3] == ["Saturated vapour", "Superheated vapour", "Saturated liquid"]
    assert labels[3].startswith("Saturated mixture (x = ")
    r2 = refrigeration_cycle("R134a", 273.15, 313.15, 10e3, superheat=5, subcooling=5)
    assert r2.states[0].state == "Superheated vapour"
    assert r2.states[2].state == "Compressed (subcooled) liquid"


def test_refrigeration_cycle_out_of_range_raises():
    with pytest.raises(ValueError):
        refrigeration_cycle("R134a", 273.15, 473.15, 10e3)  # above critical temperature


def test_refrigerant_info_has_gwp_for_r134a():
    info = refrigerant_info("R134a")
    assert info["GWP100"] == pytest.approx(1430, rel=0.05)


# ---------------- psychrometrics, cooling tower, vacuum ----------------

def test_psychrometrics_ashrae():
    assert atmospheric_pressure(0) == pytest.approx(101325, rel=1e-6)
    s = moist_air_state(298.15, 0.5)
    assert s.humidity_ratio == pytest.approx(0.00988, rel=0.01)  # ASHRAE chart at 25 °C, 50 %
    assert s.T_dew < s.T_wet < s.T_dry


def test_cooling_tower_energy_balance_and_guards():
    r = cooling_tower(80e3, 304.15, 297.15, 0.6, 3.0)
    assert r.water_flow * 4186 * r.range == pytest.approx(80e3)
    assert r.makeup == pytest.approx(r.evaporation + r.drift + r.blowdown)
    with pytest.raises(ValueError):
        cooling_tower(80e3, 290.15, 297.15, 0.6, 3.0)
    with pytest.raises(ValueError):
        cooling_tower(80e3, 304.15, 297.15, 0.6, 3.0, cycles_of_concentration=1.0)


def test_vacuum_pumpdown_and_continuous_load():
    r = pumpdown(1.0, 83000, 5000, 60.0, 298.15)
    assert r.pump_speed == pytest.approx(1 / 60 * math.log(83000 / 5000))
    assert r.molar_mass == pytest.approx(0.02897, rel=1e-3)
    c = continuous_load(20000, 373.15, 50 / 3600, 2 / 3600)
    assert c.y_steam + c.y_co2 == pytest.approx(1.0)
    with pytest.raises(ValueError):
        continuous_load(101325, 350.0, 0.01, 0.001)  # water not superheated
