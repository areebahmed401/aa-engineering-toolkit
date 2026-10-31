"""Runtime environment flags."""
import importlib.util
import sys

# True when running inside Pyodide (the web app). Features needing native libraries
# that Pyodide lacks (e.g. PyBaMM) check this and hide themselves.
IN_BROWSER = sys.platform == "emscripten"


def has_package(name: str) -> bool:
    """True if an optional dependency is importable, without importing it."""
    return importlib.util.find_spec(name) is not None
