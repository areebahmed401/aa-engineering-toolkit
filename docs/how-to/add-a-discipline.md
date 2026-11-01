# Add a discipline

## 1. Copy the template

Copy `src/engtoolkit/_template/` to `src/engtoolkit/<discipline>/`:

```
models/       pure calculations returning Result dataclasses (SI units)
plots.py      matplotlib figures (return a Figure, never call plt.show())
tools.py      @register_tool("<discipline>.<name>", ...) registrations
data/         data files; CSV starts with "# source: ...", YAML entries have a source: key
__init__.py   public API
```

## 2. Register the section

Add it to `SECTIONS` in `src/engtoolkit/core/registry.py`:

```python
SECTIONS = {
    "thermo": "Thermodynamics & Fluids",
    ...
    "mydiscipline": "My Discipline",
}
```

`load_tools()` imports `engtoolkit.<section>.tools` for each section, and tool ids must start with a
section key.

## 3. Add an import-linter contract

Layers are enforced by `lint-imports`. Add a contract to `pyproject.toml` that forbids the new package
from importing disciplines it must not depend on, for example:

```toml
[[tool.importlinter.contracts]]
name = "mydiscipline may use thermo but not structural"
type = "forbidden"
source_modules = ["engtoolkit.mydiscipline"]
forbidden_modules = ["engtoolkit.structural", "engtoolkit.asme"]
```

Also add the new package to the `forbidden_modules` of the `core`, and `materials`/`catalogs`
contracts so the foundations never import it.

## 4. Tests, docs, web

- Tests in `tests/<discipline>/` with a `test_tool_<name>` per tool.
- A page in `docs/reference/` with `::: engtoolkit.<discipline>...` and a nav entry in `mkdocs.yml`.
- The web app picks up the section and its tools from `export_schema()` when
  `python scripts/build_web_assets.py` runs. Section icon and colour are set in `SECTION_META` in
  `web/src/components/ui.tsx` and the colour in `branding/theme.json`.
