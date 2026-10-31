"""Material model: grouped properties, optionally temperature dependent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from engtoolkit.core.data import to_float

# Property groups and the properties each may hold (SI units)
PROPERTY_GROUPS = {
    "mechanical": {
        "E": "Pa", "nu": "", "G": "Pa", "rho": "kg/m^3",
        "yield_strength": "Pa", "ultimate_strength": "Pa", "fatigue_limit": "Pa",
    },
    "thermal": {
        "k": "W/(m·K)", "cp": "J/(kg·K)", "alpha": "1/K", "emissivity": "", "max_service_T": "K",
    },
    "electrical": {"resistivity": "Ω·m", "conductivity": "S/m", "permittivity": ""},
    "surface": {"roughness": "m"},
    "allowables": {"S": "Pa"},
}
UNITS = {name: unit for group in PROPERTY_GROUPS.values() for name, unit in group.items()}

REFERENCE_T = 293.15  # K, temperature used when a curve is read without a temperature


@dataclass(frozen=True)
class TemperatureCurve:
    """Tabulated property vs temperature [K], linearly interpolated (clamped at the ends)."""
    T: tuple[float, ...]
    values: tuple[float, ...]

    def __call__(self, T: float | None = None) -> float:
        T = REFERENCE_T if T is None else T
        return float(np.interp(T, self.T, self.values))

    @property
    def range(self) -> tuple[float, float]:
        return self.T[0], self.T[-1]


def _parse_value(raw: Any, name: str):
    """A scalar, or a curve given as {T_C: [...], value: [...]} / {T_K: [...], value: [...]}."""
    if isinstance(raw, dict):
        if "T_C" in raw:
            T = [to_float(t) + 273.15 for t in raw["T_C"]]
        elif "T_K" in raw:
            T = [to_float(t) for t in raw["T_K"]]
        else:
            raise ValueError(f"Curve for {name!r} needs T_C or T_K")
        values = [to_float(v) for v in raw["value"]]
        if len(T) != len(values) or len(T) < 2:
            raise ValueError(f"Curve for {name!r} needs matching T and value lists (2+ points)")
        order = np.argsort(T)
        return TemperatureCurve(tuple(np.array(T)[order]), tuple(np.array(values)[order]))
    return to_float(raw)


@dataclass
class Material:
    name: str
    family: str = "other"
    properties: dict[str, float | TemperatureCurve] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    source: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Material":
        props: dict[str, float | TemperatureCurve] = {}
        for group, allowed in PROPERTY_GROUPS.items():
            for key, raw in (data.get(group) or {}).items():
                if key.endswith("_C") and key[:-2] in allowed:  # e.g. max_service_T_C
                    props[key[:-2]] = to_float(raw) + 273.15
                    continue
                if key not in allowed:
                    raise ValueError(f"{data.get('name')}: unknown {group} property {key!r}")
                props[key] = _parse_value(raw, key)
        return cls(
            name=data["name"],
            family=data.get("family", "other"),
            properties=props,
            aliases=tuple(data.get("aliases", ())),
            source=data.get("source", ""),
            notes=data.get("notes", ""),
        )

    # ---------------- access ----------------
    def has(self, name: str) -> bool:
        return name in self.properties or (name == "G" and {"E", "nu"} <= self.properties.keys())

    def prop(self, name: str, T: float | None = None) -> float:
        """Property value in SI units, evaluated at temperature T [K] if it is temperature dependent."""
        if name == "G" and "G" not in self.properties and {"E", "nu"} <= self.properties.keys():
            return self.prop("E", T) / (2 * (1 + self.prop("nu", T)))
        try:
            value = self.properties[name]
        except KeyError:
            raise KeyError(f"Material {self.name!r} has no property {name!r}") from None
        return value(T) if isinstance(value, TemperatureCurve) else value

    def get(self, name: str, T: float | None = None, default: float | None = None) -> float | None:
        return self.prop(name, T) if self.has(name) else default

    def is_temperature_dependent(self, name: str) -> bool:
        return isinstance(self.properties.get(name), TemperatureCurve)

    def table(self) -> list[dict[str, Any]]:
        """Properties at the reference temperature, for display."""
        rows = []
        for group, allowed in PROPERTY_GROUPS.items():
            for key in allowed:
                if self.has(key):
                    rows.append({"group": group, "property": key, "value": self.prop(key), "unit": UNITS[key],
                                 "temperature_dependent": self.is_temperature_dependent(key)})
        return rows

    # ---------------- convenience attributes (reference temperature) ----------------
    E = property(lambda self: self.get("E"))
    nu = property(lambda self: self.get("nu"))
    G = property(lambda self: self.get("G"))
    rho = property(lambda self: self.get("rho"))
    yield_strength = property(lambda self: self.get("yield_strength"))
    ultimate_strength = property(lambda self: self.get("ultimate_strength"))
    k = property(lambda self: self.get("k"))
    cp = property(lambda self: self.get("cp"))
    alpha = property(lambda self: self.get("alpha"))
    emissivity = property(lambda self: self.get("emissivity"))
    roughness = property(lambda self: self.get("roughness"))
    resistivity = property(lambda self: self.get("resistivity"))
    # older names used in the notebooks
    thermal_conductivity = k
    specific_heat = cp

    def __repr__(self) -> str:
        return f"Material({self.name!r}, family={self.family!r})"
