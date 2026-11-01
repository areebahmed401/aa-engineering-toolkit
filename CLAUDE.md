# AA Engineering Toolkit: notes for Claude (Chef, Workers, Testers)

Python package `engtoolkit` (src/) + React/Pyodide web app (web/) deployed to GitHub Pages on every push to `main`.
Work is run with the user-level `kitchen-brigade` skill: only Chef commits, pushes and merges.

## Environment (Windows)
- Python venv: `C:\Users\ahmed\.venvs\engineering-toolkit\Scripts\python.exe` (short path because of the Windows 260-char limit; the repo lives at `C:\dev\engineering-toolkit`). Worktrees use `C:\Users\ahmed\.venvs\etk-<name>`.
- Node: in PowerShell refresh PATH first:
  `$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")`
- PowerShell 5.1 mangles quotes in `python -c "..."`: write a script file instead.
- `Set-Content -Encoding utf8` writes a BOM: edit files with the Edit tool.
- gh: `C:\Program Files\GitHub CLI\gh.exe`.

## Checks (fast first)
```
python -m ruff check src tests
lint-imports
python -m pytest -q
python scripts/build_web_assets.py      # needed before web build/e2e: writes web/public/py (gitignored)
cd web; npm run typecheck; npm test; npm run build
cd web; npx playwright test --reporter=line   # slow; thermo.refrigeration_cycle loads CoolProp HEOS and can time out locally (CI passes it): add --grep-invert "refrigeration_cycle" locally
```
Send long output to a file and read the summary.

## Rules
- `notebooks/` is frozen (to be deprecated): don't add or edit notebooks. CI still runs them with nbmake; if a change breaks one, stop and tell Chef.
- Units are SI internally; temperature differences use unit `ΔK`; display conversion lives in `web/src/lib/units.ts`.
- Every registered tool needs a `test_tool_<name>` test. Dependency layers are enforced by import-linter.
- Colours come from `branding/theme.json`, mirrored as RGB triplets in `web/src/index.css`; don't hard-code hex in components.
- Don't reproduce copyrighted code tables (ASME etc.); reference PDFs stay in gitignored `references/`.
