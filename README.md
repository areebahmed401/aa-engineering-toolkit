<p align="center">
  <img src="branding/aa-wordmark.svg" alt="AA Engineering Toolkit" width="420">
</p>

*Areeb Ahmed | Mechanical Engineer*

Engineering calculations as a Python package (`engtoolkit`) used by Jupyter notebooks and by a web
app that runs the same package in your browser. Four disciplines share one materials database and
one set of standard catalogs: **Thermodynamics & Fluids, Structural, Electrical (battery) and ASME**.

**▶ Web app: <https://areebahmed401.github.io/aa-engineering-toolkit/>** (no install; Python runs
locally in the browser via Pyodide, so nothing you enter leaves your device).

## Web app

`web/` is a React + TypeScript + Tailwind front end. Python runs in a Web Worker (Pyodide) and the
input forms, result cards and interactive Plotly charts are generated from the tool registry, so a
new registered tool appears in the app without front-end code. Inputs are encoded in the URL, so a
link reproduces a calculation, and results download as a Markdown report or CSV.

```bash
python scripts/build_web_assets.py   # wheel + tool schema + dropdown choices -> web/public/py
cd web
npm install
npm run dev                          # http://localhost:5173
npm test                             # unit tests;  npm run e2e  runs every tool in Chromium
```

Water and steam default to IAPWS-IF97 and convection uses tabulated air, both instant in the
browser. Refrigerants and other CoolProp fluids load CoolProp's full fluid library on first use,
which takes about a minute in the browser.

> **Disclaimer:** this toolkit is for learning, estimation and preliminary design. It is not a
> substitute for design by a qualified engineer or for checks against the current edition of the
> applicable codes and standards (ASME, API, EN, etc.). Verify every result before relying on it.

## What's inside

| Package | Contents |
|---|---|
| `engtoolkit.materials` | Shared properties for every discipline: metals, polymers, composites, insulation (temperature-dependent curves, each with a source) and fluids via CoolProp (`fluid("Water")`, `fluid("IF97::Water")`, `fluid("INCOMP::MEG[0.3]")`) |
| `engtoolkit.catalogs` | ASME B36.10/B36.19 pipe schedules 10/40/80, EN 10365 IPE profiles, Crane TP-410 fitting data, supplier costs, battery cells (LG M50 NMC, A123 LFP, 60 Ah pouch) |
| `engtoolkit.thermo` | Fluid properties, steam tables (IAPWS-95 / IF97), pipe pressure drop (Colebrook + Crane), heat transfer correlations, insulation sizing with natural convection + radiation, refrigeration/heat-pump cycle, psychrometrics, cooling towers, vacuum pumps |
| `engtoolkit.structural` | Sections (rectangle, tubes, circle, I/H, C, T, Z, L, catalog profiles) with properties and outlines, determinacy check, equilibrium and 2D FEM (Euler-Bernoulli / Timoshenko), torsion and warping |
| `engtoolkit.electrical` | Battery modelling: 1RC/2RC equivalent circuit with OCV-SOC and cut-offs (CC, CP, CC-CV, drive cycle), lumped thermal model with air or water-glycol cold-plate cooling, calendar/cycle aging (Wang 2011, Schmalstieg 2014), PyBaMM DFN/SPM with SEI and lithium plating (optional `[battery]` extra, precomputed for the browser) |
| `engtoolkit.asme` | ASME VIII Div 1 vessel sizing — next phases |
| `engtoolkit.core` | Units (SI inside, pint at the edges), result objects, the tool registry, plotting style |

Every calculation the web app will expose is a registered **tool** with labelled, unit-tagged inputs
and a validation test against a cited reference:

```python
import engtoolkit
engtoolkit.run("thermo.insulation_thickness", dn=100, T_fluid=453.15, q_max=50)
engtoolkit.run("structural.beam_analysis", {"length": 3.0, "right_support": "pinned"})
[t.id for t in engtoolkit.list_tools()]
```

Units are SI throughout (m, N, Pa, K, W). Beam sign convention: loads `P`, `w` positive downward,
applied moments positive counter-clockwise, deflection positive upward, sagging moment positive.

## Repository layout

```
src/engtoolkit/   the package (core, materials, catalogs, thermo, structural, electrical, asme, _template)
notebooks/        structural/, thermo/, asme/, electrical/ (+ 00_overview.ipynb)
tests/            one folder per package; every tool has a test_tool_<name> validation test
branding/         logo, theme colours (theme.json), matplotlib style
```

Reference documents (codes, standards, vendor catalogues) are not distributed with this repo.
Keep your own copies in a local `references/` folder, which git ignores.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows (macOS/Linux: source venv/bin/activate)
pip install -r requirements-dev.txt
pip install -e ".[dev,notebook]"
```

In VS Code, open the folder, open a notebook and pick the `venv` interpreter as the kernel.

> **Windows tip:** if `pip install` fails with a "path too long" error, either enable Windows long
> paths or create the virtual environment at a short path (for example `C:\venvs\etk`) and select
> that interpreter in VS Code.

## Example

```python
from engtoolkit.structural import Beam, IBeam, Fixed, Pinned, PointLoad, analyze_beam

b = Beam("S355", length=4.0, shape=IBeam.from_profile("IPE 200"))
b.set_end_conditions(Fixed(), Pinned())      # statically indeterminate -> FEM
b.add_load(PointLoad(P=20e3, x=2.0))
result = analyze_beam(b)
result.summary()                             # reactions, max moment, stress, utilisation
result.plot()                                # deflection / slope / shear / moment diagrams
```

## Adding to the toolkit

- **A material:** add an entry with a `source` to `src/engtoolkit/materials/data/*.yaml`.
- **A tool:** write the calculation (returning a `Result`), register it in the discipline's `tools.py`
  with `@register_tool(...)` and a reference, and add a `test_tool_<name>` test. The web app picks it up.
- **A discipline:** copy `src/engtoolkit/_template/` and follow its instructions.

Dependency direction is enforced by `lint-imports`: `core` ← `materials`/`catalogs` ← `thermo` ←
`electrical`, and `structural` ← `asme`.

## Tests

```bash
pytest                                   # unit + tool validation tests
pytest --nbmake notebooks                # every notebook runs top to bottom
lint-imports                             # dependency layers
ruff check src tests
```

All of these run on GitHub Actions for every push.

## License

[MIT](LICENSE) © 2026 Areeb Ahmed
