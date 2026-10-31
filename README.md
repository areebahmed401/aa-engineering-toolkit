# Engineering Toolkit (Jupyter)

*Areeb Ahmed | Mechanical Engineer*

Engineering notebooks for structural, thermofluids and ASME code calculations, backed by a small
Python library (`utils`) that the notebooks import.

## Contents

| Folder | What's in it |
|---|---|
| `0. overview.ipynb` | Index of the toolkit |
| `1. Structural/` | Statics (FBD, FEM and determinate solvers), bending, torsion & warping, plus outlines for shear-flexible beams, buckling and Maxwell-Mohr. `RWTH/` holds course examples |
| `2. Fluids/` | Pipe sizing: Darcy-Weisbach with Crane TP-410 fittings, velocity / pressure drop / cost vs pipe size |
| `3. ASME/` | Notes on ASME VIII Div 1 pressure vessels and B31.3 process piping |
| `utils/Appendix/` | The library: materials, unit converters, formulas, `structural/` (sections, loads, solvers, torsion) and `thermofluids/` (pipe flow, refrigeration cycle, cooling tower, insulation, p-h / T-s diagrams) |
| `utils/Catalogs/` | CSV data: Sch 40 pipe sizes and costs, fittings, valves, Crane L/D values |
| `Images/`, `Resources/` | Diagrams and reference documents |
| `tests/` | Unit tests that check the library against textbook results |

Units are SI throughout (m, N, Pa, K unless a name says otherwise).

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
pip install -e .               # installs utils so notebooks can import it from any folder
```

In VS Code, open the folder, open a notebook and pick the `venv` interpreter as the kernel.

> **Windows tip:** if `pip install` fails with a "path too long" error, either enable Windows long
> paths or create the virtual environment at a short path (for example `C:\venvs\etk`) and select
> that interpreter in VS Code.

## Using the library

```python
from utils.Appendix.materials import get_material
from utils.Appendix.structural import beam, I_beam, Fixed, Free, PointLoad, FEMSolver

b = beam(get_material("Steel"), length=2.0, shape=I_beam(0.2, 0.02, 0.3, 0.01))
b.set_end_conditions(Fixed(), Free())
b.add_load(PointLoad(P=10e3, x=2.0))      # downward positive

solver = FEMSolver(b, n_elem=50)
solver.solve()
print(solver.reactions())
solver.plot_results()
```

Sign convention for beams: loads `P`, `w` positive downward, applied moments positive
counter-clockwise, deflection positive upward, sagging bending moment positive.

## Tests

```bash
pytest                                     # library unit tests
pytest --nbmake "0. overview.ipynb" "1. Structural" "2. Fluids" "3. ASME"   # every notebook runs
```

Both run on GitHub Actions for every push.
