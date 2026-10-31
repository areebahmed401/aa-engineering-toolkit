"""
Build the Python assets the web app loads: the engtoolkit wheel, the tool schema and dropdown choices.

    python scripts/build_web_assets.py          # writes web/public/py/

The web app reads manifest.json to know which wheel to install and which Pyodide packages to preload.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "py"
PYODIDE_VERSION = "314.0.7"
# Loaded before the wheel is installed; anything else (scipy, pandas, matplotlib, pint) loads on demand.
PYODIDE_PACKAGES = ["micropip", "numpy", "coolprop", "pydantic", "pyyaml"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.whl"):
        old.unlink()
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(OUT)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    wheel = next(OUT.glob("*.whl")).name

    from engtoolkit import __version__
    from engtoolkit.webapi import choices_json, schema_json

    (OUT / "schema.json").write_text(schema_json(), encoding="utf-8")
    (OUT / "choices.json").write_text(choices_json(), encoding="utf-8")
    manifest = {"version": __version__, "wheel": wheel, "pyodide": PYODIDE_VERSION, "packages": PYODIDE_PACKAGES}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"web assets written to {OUT.relative_to(ROOT)}: {wheel}, schema.json, choices.json, manifest.json")


if __name__ == "__main__":
    main()
