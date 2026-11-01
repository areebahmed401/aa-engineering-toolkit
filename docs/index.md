# AA Engineering Toolkit

A Python package and a browser app for everyday engineering calculations. Every calculation is a
*tool*: a typed set of inputs, a function and a cited reference it is validated against.

## Disciplines

| Discipline | Package | Covers |
|---|---|---|
| Thermodynamics & Fluids | `engtoolkit.thermo` | Pipe pressure drop, insulation, steam tables, refrigeration cycles, psychrometrics, cooling towers, vacuum |
| Structural | `engtoolkit.structural` | Cross sections, beams, determinacy, 2D FEM, torsion |
| Electrical | `engtoolkit.electrical` | Battery equivalent-circuit, thermal and ageing models |
| ASME | `engtoolkit.asme` | Section VIII Div. 1 shells, heads, nozzles, external pressure |

Shared foundations live in `engtoolkit.core` (registry, results, units), `engtoolkit.materials`
and `engtoolkit.catalogs`.

## Web app

The same package runs in the browser through Pyodide, with forms generated from the tool registry:
[open the web app](https://areebahmed401.github.io/aa-engineering-toolkit/).

## Install

```bash
pip install -e .
```

See [Getting started](getting-started.md) for the release wheel, extras and a first calculation.

!!! warning
    Results are for preliminary design. Verify against the governing standard before relying on them.
