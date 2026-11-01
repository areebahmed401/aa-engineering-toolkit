# Add a material

Solid materials are YAML entries in `src/engtoolkit/materials/data/`, one file per family
(`metals.yaml`, `nonmetals.yaml`, `insulation.yaml`). They load automatically on first use by
`engtoolkit.materials.library`.

## Entry format

Values are SI. Every entry needs a `source`. A property is a constant or a temperature curve
`{T_C: [...], value: [...]}`:

```yaml
materials:
  - name: ASTM A106B
    family: metal
    aliases: [Carbon Steel, A106 Grade B, A106B]
    source: ASTM A106 minimum strengths; thermal properties typical of carbon steel (Incropera, Table A.1)
    mechanical:
      E: {T_C: [20, 100, 200, 300, 400], value: [207e9, 203e9, 196e9, 189e9, 179e9]}
      nu: 0.3
      rho: 7850
      yield_strength: 240e6
    thermal:
      k: {T_C: [20, 100, 200, 300, 400], value: [50, 49, 47, 44, 41]}
      cp: 480
    surface: {roughness: 4.5e-5}
```

Property groups are `mechanical`, `thermal`, `surface` and `electrical`, plus `allowables` for code
stresses you enter and verify yourself (do not copy code tables into the repository).

## Use it

```python
from engtoolkit.materials import get_material

steel = get_material("a106b")          # name or alias, case-insensitive
steel.prop("k", T=473.15)              # temperature-dependent conductivity [W/m·K]
```

Names and aliases must be unique, otherwise loading raises `ValueError`.

## Without editing the package

```python
from engtoolkit.materials import load_materials
load_materials("my_materials.yaml")    # file path or YAML text
```

Tool inputs declared with `{"choices": "materials:metal"}` list the materials of that family, so a new
metal shows up in the web app dropdown after rebuilding the web assets. Add a test in `tests/materials/`.
