# Add a tool

A tool is a calculation registered with `@register_tool`. The web app builds its menu and form from
the registry, so most tools need no UI code.

## 1. Write the calculation

Put pure functions in the discipline package (for example `src/engtoolkit/thermo/`). They take and
return SI values; results are dataclasses derived from `Result` with `rfield(unit, label)` fields:

```python
from dataclasses import dataclass
from engtoolkit.core.results import Result, rfield

@dataclass
class ExampleResult(Result):
    area: float = rfield("m^2", "Area")

def example_calculation(width: float, height: float) -> ExampleResult:
    """Rectangle area [m²] from width and height [m]."""
    return ExampleResult(area=width * height)
```

## 2. Register it

In the discipline's `tools.py`, declare an input model with `Input(default, unit, label, ...)` and
decorate the function. The id is `<section>.<name>` and a `reference` is mandatory:

```python
from pydantic import BaseModel
from engtoolkit.core.registry import Input, register_tool

class ExampleInputs(BaseModel):
    width: float = Input(1.0, "m", "Width", gt=0)
    height: float = Input(2.0, "m", "Height", gt=0)

@register_tool("thermo.example", "Example", ExampleInputs,
               reference="The textbook or standard the validation test checks against")
def example_tool(inp: ExampleInputs) -> ExampleResult:
    return example_calculation(inp.width, inp.height)
```

Dropdowns use `json_schema_extra={"choices": "fluids"}` or `"materials:metal"`. Optional arguments:
`description`, `tags`, `charts=` (a function returning chart specs) and `custom_page`.

## 3. Add the validation test

Every registered tool needs a `test_tool_<name>` test in `tests/<discipline>/test_tools.py` that
checks the result against the cited reference:

```python
def test_tool_example():
    assert run("thermo.example", width=2, height=3).area == pytest.approx(6)
```

## 4. Check and build

```bash
python -m ruff check src tests
lint-imports
python -m pytest -q
python scripts/build_web_assets.py
```

`scripts/build_web_assets.py` builds the wheel and writes `schema.json` from `export_schema()`, which
loads every discipline's `tools` module. A newly registered tool therefore appears in the web app
after a rebuild. Dependency layers are enforced by import-linter; see
[Add a discipline](add-a-discipline.md).
