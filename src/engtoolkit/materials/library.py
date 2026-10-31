"""
Material library: loads the YAML files in ``materials/data`` and any user-supplied files.

Add a material by adding an entry to the right family file (metals.yaml, polymers.yaml, ...),
with a ``source``. Values are SI; curves use ``{T_C: [...], value: [...]}``.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .model import Material

DATA_DIR = Path(__file__).resolve().parent / "data"

_MATERIALS: dict[str, Material] = {}
_LOOKUP: dict[str, str] = {}  # lowercase name/alias -> canonical name
_LOADED = False


def _key(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").split())


def _register(material: Material, replace: bool = False) -> Material:
    if material.name in _MATERIALS and not replace:
        raise ValueError(f"Material {material.name!r} already exists (pass replace=True to override)")
    _MATERIALS[material.name] = material
    for name in (material.name, *material.aliases):
        _LOOKUP[_key(name)] = material.name
    return material


def _load_yaml_text(text: str, source: str, replace: bool) -> list[Material]:
    data = yaml.safe_load(text) or {}
    entries = data.get("materials", data if isinstance(data, list) else [])
    return [_register(Material.from_dict(entry), replace=replace) for entry in entries]


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    for path in sorted(DATA_DIR.glob("*.yaml")):
        _load_yaml_text(path.read_text(encoding="utf-8"), path.name, replace=False)


def load_materials(path_or_text: str | Path, replace: bool = True) -> list[Material]:
    """Load extra materials from a YAML file path or YAML text (e.g. a file uploaded in the web app)."""
    _ensure_loaded()
    if isinstance(path_or_text, Path) or (isinstance(path_or_text, str) and path_or_text.strip().endswith((".yaml", ".yml"))):
        path = Path(path_or_text)
        return _load_yaml_text(path.read_text(encoding="utf-8"), path.name, replace)
    return _load_yaml_text(path_or_text, "user", replace)


def get_material(name: str | Material) -> Material:
    """Material by name or alias (case-insensitive). A Material passed in is returned as is."""
    if isinstance(name, Material):
        return name
    _ensure_loaded()
    try:
        return _MATERIALS[_LOOKUP[_key(name)]]
    except KeyError:
        raise KeyError(f"Unknown material {name!r}. Try list_materials().") from None


def list_materials(family: str | None = None) -> list[str]:
    _ensure_loaded()
    return sorted(m.name for m in _MATERIALS.values() if family is None or m.family == family)


def families() -> list[str]:
    _ensure_loaded()
    return sorted({m.family for m in _MATERIALS.values()})


def add_material(name: str, family: str = "other", source: str = "user", replace: bool = False,
                 aliases: tuple[str, ...] = (), **groups) -> Material:
    """
    Add a material in code: ``add_material("My steel", "metal", mechanical={"E": 205e9, ...})``.
    Property groups: mechanical, thermal, electrical, surface, allowables.
    """
    _ensure_loaded()
    data = {"name": name, "family": family, "source": source, "aliases": list(aliases), **groups}
    return _register(Material.from_dict(data), replace=replace)
