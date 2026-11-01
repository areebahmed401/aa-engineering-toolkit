"""
Physics-based cell models with PyBaMM (optional extra: ``pip install -e ".[battery]"``).

PyBaMM needs compiled solvers that are not available in the browser, so this module is used in
notebooks and by ``scripts/generate_battery_reference.py``, which writes a precomputed grid to
``electrical/data/pybamm_reference.json`` that the web app plots next to the equivalent-circuit model.

All runs model the LG M50 21700 cell:
- discharge: DFN (Doyle-Fuller-Newman) with a lumped thermal model, "Chen2020" parameters
  (Chen et al. 2020, J. Electrochem. Soc. 167, 080534)
- degradation: SPM with solvent-diffusion-limited SEI growth and partially reversible lithium plating
  (with porosity change) and lumped thermal, "OKane2022" parameters (O'Kane et al. 2022,
  Phys. Chem. Chem. Phys. 24, 7909)
- ``fit_ecm``: 2RC equivalent-circuit parameters fitted to a DFN constant-current pulse

PyBaMM: Sulzer et al. (2021), J. Open Res. Softw. 9(1), 14.
"""
from __future__ import annotations

import numpy as np


def _pybamm():
    try:
        import pybamm
    except ImportError as err:  # pragma: no cover - depends on the environment
        raise ImportError("PyBaMM is an optional extra: pip install -e \".[battery]\"") from err
    pybamm.set_logging_level("ERROR")
    return pybamm


def available() -> bool:
    try:
        _pybamm()
        return True
    except ImportError:
        return False


LAYERS = ("Negative current collector", "Negative electrode", "Separator", "Positive electrode",
          "Positive current collector")


def lumped_heat_capacity(pv) -> float:
    """Heat capacity [J/K] of PyBaMM's lumped thermal model: thickness-averaged ρ·cp of the layers × cell volume."""
    rho_c = sum(pv[f"{p} density [kg.m-3]"] * pv[f"{p} specific heat capacity [J.kg-1.K-1]"] * pv[f"{p} thickness [m]"]
                for p in LAYERS)
    return rho_c / sum(pv[f"{p} thickness [m]"] for p in LAYERS) * pv["Cell volume [m3]"]


def parameters(name: str = "Chen2020", T_ambient: float = 298.15, h: float = 10.0,
               heat_capacity: float | None = None, area: float | None = None):
    """
    PyBaMM parameter values at an ambient (= initial) temperature [K] and heat transfer coefficient.
    ``heat_capacity`` [J/K] and ``area`` [m²] make the lumped thermal model match a catalog cell (the
    layer specific heats are scaled; PyBaMM's default only counts the jelly roll, about 43 J/K for the M50).
    """
    pybamm = _pybamm()
    pv = pybamm.ParameterValues(name)
    pv.update({"Ambient temperature [K]": T_ambient, "Initial temperature [K]": T_ambient,
               "Total heat transfer coefficient [W.m-2.K-1]": h})
    if heat_capacity is not None:
        scale = heat_capacity / lumped_heat_capacity(pv)
        pv.update({f"{p} specific heat capacity [J.kg-1.K-1]": pv[f"{p} specific heat capacity [J.kg-1.K-1]"] * scale
                   for p in LAYERS})
    if area is not None:
        pv.update({"Cell cooling surface area [m2]": area})
    return pv


def ocv_table(soc_points, name: str = "Chen2020") -> np.ndarray:
    """Equilibrium cell OCV [V] at each SOC, from the electrode OCP functions and the cell's stoichiometry window."""
    pybamm = _pybamm()
    pv = pybamm.ParameterValues(name)
    T = pybamm.Scalar(298.15)

    def ocp(key, sto):
        fn = pv[key]
        return fn(pybamm.Scalar(sto)) if fn.__code__.co_argcount == 1 else fn(pybamm.Scalar(sto), T)

    out = []
    for s in soc_points:
        p = pv.set_initial_state(float(s), inplace=False)
        x = p["Initial concentration in negative electrode [mol.m-3]"] / p["Maximum concentration in negative electrode [mol.m-3]"]
        y = p["Initial concentration in positive electrode [mol.m-3]"] / p["Maximum concentration in positive electrode [mol.m-3]"]
        out.append(float((ocp("Positive electrode OCP [V]", y) - ocp("Negative electrode OCP [V]", x)).evaluate()))
    return np.array(out)


def discharge(c_rate: float = 1.0, T_ambient: float = 298.15, h: float = 10.0, model: str = "DFN",
              n_points: int = 80, heat_capacity: float | None = None, area: float | None = None) -> dict:
    """Constant-current discharge to 2.5 V from full charge. Returns downsampled time series (SI)."""
    pybamm = _pybamm()
    m = getattr(pybamm.lithium_ion, model)(options={"thermal": "lumped"})
    exp = pybamm.Experiment([f"Discharge at {c_rate}C until 2.5 V"], period=f"{max(1.0, 10.0 / c_rate):g} seconds")
    sol = pybamm.Simulation(m, parameter_values=parameters("Chen2020", T_ambient, h, heat_capacity, area),
                             experiment=exp).solve(initial_soc=1.0)
    t = sol["Time [s]"].entries
    t = t - t[0]
    grid = np.linspace(0.0, t[-1], n_points)
    pick = lambda name: np.interp(grid, t, sol[name].entries)
    return {
        "c_rate": c_rate, "T_ambient": T_ambient, "h": h, "model": model,
        "time": grid, "capacity_Ah": pick("Discharge capacity [A.h]"), "voltage": pick("Voltage [V]"),
        "temperature": pick("X-averaged cell temperature [K]"), "heat": pick("Total heating [W]"),
    }


def degradation(c_rate: float = 1.0, T_ambient: float = 298.15, n_cycles: int = 300, h: float = 10.0,
                c_rate_charge: float = 0.5, save_every: int = 10, heat_capacity: float | None = None,
                area: float | None = None) -> dict:
    """
    Repeated cycles (discharge at c_rate to 2.5 V, CC-CV charge at c_rate_charge to 4.2 V / C/20, 10 min
    rests) with SEI growth and lithium plating. Returns capacity and loss mechanisms every ``save_every`` cycles.
    """
    pybamm = _pybamm()
    opts = {"SEI": "solvent-diffusion limited", "SEI porosity change": "true",
            "lithium plating": "partially reversible", "lithium plating porosity change": "true",
            "thermal": "lumped"}
    cycle = (f"Discharge at {c_rate}C until 2.5 V", "Rest for 10 minutes",
             f"Charge at {c_rate_charge}C until 4.2 V", "Hold at 4.2 V until C/20", "Rest for 10 minutes")
    exp = pybamm.Experiment([cycle] * n_cycles, period="2 minutes")
    sim = pybamm.Simulation(pybamm.lithium_ion.SPM(opts), experiment=exp,
                            parameter_values=parameters("OKane2022", T_ambient, h, heat_capacity, area))
    sol = sim.solve(initial_soc=1.0, save_at_cycles=save_every)
    summary = sol.summary_variables
    cycles = np.asarray(summary["Cycle number"], dtype=float)
    cap = np.asarray(summary["Capacity [A.h]"], dtype=float)
    out = {
        "c_rate": c_rate, "c_rate_charge": c_rate_charge, "T_ambient": T_ambient, "h": h,
        "cycles": cycles, "capacity_Ah": cap, "capacity": cap / cap[0],
        "lli": np.asarray(summary["Loss of lithium inventory [%]"], dtype=float),
    }
    for key, name in (("li_sei", "Loss of capacity to negative SEI [A.h]"),
                      ("li_plating", "Loss of capacity to negative lithium plating [A.h]")):
        try:
            out[key] = np.asarray(summary[name], dtype=float)
        except KeyError:
            pass
    keep = (cycles == 1) | (cycles % save_every == 0)  # summary variables cover every cycle; thin them out
    return {k: v[keep] if isinstance(v, np.ndarray) else v for k, v in out.items()}


def fit_ecm(T: float = 298.15, soc: float = 0.6, c_rate: float = 1.0, duration: float = 300.0) -> dict:
    """
    2RC parameters fitted to a DFN constant-current pulse (isothermal): overpotential = bulk OCV - V
    fitted with I·(R0 + R1·(1 - e^(-t/τ1)) + R2·(1 - e^(-t/τ2))). Needs SciPy.
    """
    pybamm = _pybamm()
    from scipy.optimize import curve_fit

    pv = parameters("Chen2020", T, 10.0)
    I = c_rate * pv["Nominal cell capacity [A.h]"]
    exp = pybamm.Experiment([f"Discharge at {c_rate}C for {duration:g} seconds"], period="0.5 seconds")
    sol = pybamm.Simulation(pybamm.lithium_ion.DFN(), parameter_values=pv, experiment=exp).solve(initial_soc=soc)
    t = sol["Time [s]"].entries
    t = t - t[0]
    eta = sol["Bulk open-circuit voltage [V]"].entries - sol["Voltage [V]"].entries

    def model(t, R0, R1, tau1, R2, tau2):
        return I * (R0 + R1 * (1 - np.exp(-t / tau1)) + R2 * (1 - np.exp(-t / tau2)))

    popt, _ = curve_fit(model, t[1:], eta[1:], p0=[0.02, 0.005, 5.0, 0.01, 100.0],
                        bounds=([0, 0, 0.2, 0, 10], [0.2, 0.2, 50, 0.2, 5000]))
    rms = float(np.sqrt(np.mean((model(t[1:], *popt) - eta[1:]) ** 2)))
    R0, R1, tau1, R2, tau2 = (float(v) for v in popt)
    return {"T": T, "soc": soc, "c_rate": c_rate, "R0": R0, "R1": R1, "tau1": tau1, "R2": R2, "tau2": tau2,
            "rms_V": rms}
