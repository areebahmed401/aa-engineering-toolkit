"""Fast fluid paths used by the web app: tabulated air, IF97 water and lazy CoolProp loading."""
import os
import subprocess
import sys
import textwrap

import pytest

from engtoolkit.materials import AIR, WATER, fluid, needs_fluid_library


@pytest.mark.parametrize("T", [280.0, 350.0, 450.0, 600.0])
def test_tabulated_air_matches_coolprop_reference(T):
    table = fluid(AIR).state(T=T, P=101325)
    ref = fluid("Air").state(T=T, P=101325)
    assert table.rho == pytest.approx(ref.rho, rel=0.01)
    assert table.mu == pytest.approx(ref.mu, rel=0.02)
    assert table.k == pytest.approx(ref.k, rel=0.03)
    assert table.cp == pytest.approx(ref.cp, rel=0.01)


def test_tabulated_air_range_and_inputs():
    with pytest.raises(ValueError):
        fluid(AIR).state(T=1500)
    with pytest.raises(ValueError):
        fluid(AIR).state(T=300, Q=1)


def test_if97_water_matches_iapws95():
    a = fluid(WATER).state(T=298.15, P=101325)
    b = fluid("Water").state(T=298.15, P=101325)
    assert a.rho == pytest.approx(b.rho, rel=1e-4)
    assert a.mu == pytest.approx(b.mu, rel=1e-3)
    assert fluid(WATER).T_critical == pytest.approx(647.096, rel=1e-5)


def test_if97_transport_properties_are_not_stale():
    """CoolProp's IF97 backend caches viscosity across updates; each state must be computed fresh."""
    w = fluid(WATER)
    liquid = w.state(T=298.15, P=101325)
    vapour = w.state(T=373.15, Q=1)
    liquid_again = w.state(T=298.15, P=101325)
    assert vapour.mu == pytest.approx(1.22e-5, rel=0.02)  # saturated steam at 100 °C
    assert liquid.mu == pytest.approx(8.90e-4, rel=0.01)
    assert liquid_again.mu == pytest.approx(liquid.mu)
    assert liquid_again.k == pytest.approx(liquid.k)


def test_needs_fluid_library():
    assert needs_fluid_library("Water") and needs_fluid_library("R134a") and needs_fluid_library("HEOS::Air")
    assert not needs_fluid_library(WATER)
    assert not needs_fluid_library("INCOMP::MEG[0.3]")
    assert not needs_fluid_library(AIR)


def test_browser_tools_do_not_load_the_heos_library():
    """
    With lazy CoolProp loading (what the browser does), the IF97/air/coolant tools must not trigger the
    HEOS library load. Detected by timing: the first HEOS state afterwards still pays the library load
    (~1-2 s), which would be ~1 ms if something had loaded it already.
    """
    code = textwrap.dedent("""
        import time, engtoolkit
        for tool in ["thermo.fluid_properties", "thermo.saturated_steam_table", "thermo.pipe_pressure_drop",
                     "thermo.insulation_thickness", "thermo.insulation_heat_loss", "thermo.cooling_tower",
                     "structural.beam_analysis", "structural.section_properties", "structural.torsion"]:
            engtoolkit.run(tool)
        from engtoolkit.materials import fluid
        t = time.perf_counter()
        fluid("R134a").state(T=273.15, Q=1)
        print(time.perf_counter() - t)
    """)
    env = {**os.environ, "ENGTOOLKIT_LAZY_COOLPROP": "1"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    first_heos_seconds = float(out.stdout.strip().splitlines()[-1])
    assert first_heos_seconds > 0.2, "HEOS fluid library was already loaded by a browser-path tool"
