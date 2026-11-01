# Getting started

## Install

Requires Python 3.11 or newer.

From a release wheel (download it from the project's
[GitHub releases](https://github.com/areebahmed401/aa-engineering-toolkit/releases)):

```bash
pip install aa_engineering_toolkit-<version>-py3-none-any.whl
```

From a clone of the repository:

```bash
pip install -e .
```

Optional extras:

| Extra | Adds | Install |
|---|---|---|
| `battery` | PyBaMM models (not available in the browser) | `pip install -e ".[battery]"` |
| `notebook` | ipykernel, ipywidgets | `pip install -e ".[notebook]"` |
| `dev` | pytest, ruff, import-linter, build | `pip install -e ".[dev]"` |
| `docs` | mkdocs-material, mkdocstrings (this site) | `pip install -e ".[docs]"` |

## Find and run a tool

```python
import engtoolkit

for tool in engtoolkit.list_tools("thermo"):
    print(tool.id, "-", tool.name)

result = engtoolkit.run("thermo.pipe_pressure_drop", length=100, n_elbow_90=4)
print(result.dp_total, result.velocity)
```

`run` accepts the tool's input fields as keyword arguments (or a dict / input model). Inputs are in
SI units: Pa, K, m, kg/s. Unspecified fields use the defaults shown in the web app.

Use `engtoolkit.get_tool("thermo.pipe_pressure_drop")` to inspect a tool's `inputs` model, `reference`
and JSON `schema()`.

## Use the calculation functions directly

The tools wrap plain functions you can import:

```python
from engtoolkit.thermo import colebrook_white

f = colebrook_white(Re=1e5, roughness=4.5e-5, D=0.0525)
```

See the [API reference](reference/core.md).
