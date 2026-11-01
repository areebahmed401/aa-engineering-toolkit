"""PyBaMM models (optional extra ``[battery]``; skipped when PyBaMM is not installed, e.g. in CI)."""
import numpy as np
import pytest

pytest.importorskip("pybamm")

from engtoolkit.catalogs import get_cell  # noqa: E402
from engtoolkit.electrical.battery import pybamm_models as pm, reference  # noqa: E402

CELL = get_cell("LG M50 21700 (NMC811)")


def test_ocv_table_matches_catalog():
    ocv = pm.ocv_table([0.0, 0.5, 1.0])
    assert ocv[0] == pytest.approx(2.5, abs=1e-3) and ocv[-1] == pytest.approx(4.2, abs=1e-3)
    assert ocv[1] == pytest.approx(CELL.ocv_at(0.5), abs=2e-3)


def test_lumped_heat_capacity_matches_catalog_cell():
    pv = pm.parameters(heat_capacity=CELL.mass * CELL.cp)
    assert pm.lumped_heat_capacity(pv) == pytest.approx(CELL.mass * CELL.cp)


def test_fit_ecm_reproduces_catalog_parameters():
    fit = pm.fit_ecm(298.15)
    assert fit["rms_V"] < 2e-3
    assert fit["R0"] == pytest.approx(CELL.R0, rel=0.02)
    assert fit["R2"] == pytest.approx(CELL.R2, rel=0.05)


def test_discharge_reproduces_reference_grid():
    run = pm.discharge(1.0, 298.15, heat_capacity=CELL.mass * CELL.cp, area=CELL.surface_area)
    ref = reference.discharge(1.0, 298.15)
    assert run["capacity_Ah"][-1] == pytest.approx(ref["capacity_Ah"][-1], rel=1e-3)
    assert run["temperature"][-1] == pytest.approx(ref["temperature"][-1], abs=0.05)
    assert np.all(np.diff(run["capacity_Ah"]) >= 0)
