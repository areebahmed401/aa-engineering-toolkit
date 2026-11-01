"""
Electrical: battery modelling.

    battery/ecm.py            1RC/2RC equivalent-circuit model (browser-ready, NumPy)
    battery/thermal.py        lumped thermal model; coolant h from engtoolkit.thermo.heat_transfer
                              with engtoolkit.materials.fluid properties
    battery/aging.py          semi-empirical calendar + cycle aging (Wang 2011 LFP, Schmalstieg 2014 NMC)
    battery/reference.py      precomputed PyBaMM results (data/pybamm_reference.json)
    battery/pybamm_models.py  PyBaMM DFN/SPM with thermal + degradation (optional extra ``[battery]``,
                              imported lazily; not available in the browser)
    tools.py                  registered tools (battery simulator, cooling comparison, cycle life, PyBaMM viewer)

Cells live in ``engtoolkit.catalogs.cells``. Regenerate the PyBaMM grid with
``python scripts/generate_battery_reference.py``.

Dependency rule: electrical may import core, materials, catalogs and thermo; never structural or asme.
"""
