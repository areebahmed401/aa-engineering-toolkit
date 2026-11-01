# Electrical notebooks

- `01_ecm_thermal_aging.ipynb`: cell catalog, 2RC equivalent-circuit model, thermal coupling with air or
  water-glycol cooling (h from `engtoolkit.thermo.heat_transfer`), aging correlations at different C-rates,
  and the PyBaMM reference grid. Runs anywhere (NumPy only).
- `02_pybamm.ipynb`: PyBaMM DFN vs the equivalent circuit, ECM fitting, SEI growth and lithium plating.
  PyBaMM is an optional extra (`pip install -e ".[battery]"`); without it the notebook falls back to the
  committed reference results.
