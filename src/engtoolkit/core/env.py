"""Runtime environment flags."""
import importlib.util
import os
import sys

# True when running inside Pyodide (the web app). Features needing native libraries
# that Pyodide lacks (e.g. PyBaMM) check this and hide themselves.
IN_BROWSER = sys.platform == "emscripten"

# Import CoolProp without its package __init__ (which loads every HEOS fluid up front).
# Always on in the browser; ENGTOOLKIT_LAZY_COOLPROP=1 forces it natively (used by tests).
LAZY_COOLPROP = IN_BROWSER or os.environ.get("ENGTOOLKIT_LAZY_COOLPROP") == "1"


def has_package(name: str) -> bool:
    """True if an optional dependency is importable, without importing it."""
    return importlib.util.find_spec(name) is not None
