"""
CoolProp loader.

``import CoolProp`` runs CoolProp/__init__.py, which asks for the fluid list and so parses the whole
HEOS fluid library (~2 s natively, ~80 s in WebAssembly). In the browser we import the compiled
``CoolProp.CoolProp`` module without that ``__init__``; the HEOS library then loads only when a
HEOS fluid is first used. IF97 water/steam and incompressible coolants never need it.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types

from engtoolkit.core.env import LAZY_COOLPROP


def _load():
    if "CoolProp.CoolProp" in sys.modules:
        return sys.modules["CoolProp.CoolProp"]
    if LAZY_COOLPROP and "CoolProp" not in sys.modules:
        spec = importlib.util.find_spec("CoolProp")
        pkg = types.ModuleType("CoolProp")
        pkg.__path__ = list(spec.submodule_search_locations)
        sys.modules["CoolProp"] = pkg  # package without running __init__.py
    return importlib.import_module("CoolProp.CoolProp")


CP = _load()
