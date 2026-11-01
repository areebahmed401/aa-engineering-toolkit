# Contributing

Thanks for helping improve AA Engineering Toolkit. Docs: <https://areebahmed401.github.io/aa-engineering-toolkit/docs/>

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -e ".[dev,docs]"
cd web && npm ci               # Node 22
```

## Checks

```bash
python -m ruff check src tests
lint-imports
python -m pytest -q
mkdocs build --strict
python scripts/build_web_assets.py      # needed before web build/e2e
cd web
npm run typecheck
npm test
npm run build
npx playwright test --reporter=line     # slow; refrigeration_cycle may time out locally
```

## Branch and pull request flow

1. Branch from `main` (`git switch -c my-change`).
2. Make the change, run the checks, add a CHANGELOG entry under `[Unreleased]`.
3. Open a pull request. CI must be green before merge.

## Adding to the toolkit

- **A tool:** write the calculation (returning a `Result`), register it with `@register_tool(...)`
  in the discipline's `tools.py` with a reference, and add a `test_tool_<name>` test. The web app
  picks it up. Guide: <https://areebahmed401.github.io/aa-engineering-toolkit/docs/how-to/add-a-tool/>
- **A material:** add an entry with a `source` to `src/engtoolkit/materials/data/*.yaml`.
  Guide: <https://areebahmed401.github.io/aa-engineering-toolkit/docs/how-to/add-a-material/>
- **A discipline:** copy `src/engtoolkit/_template/` and follow its instructions.
  Guide: <https://areebahmed401.github.io/aa-engineering-toolkit/docs/how-to/add-a-discipline/>

## Rules

- SI units internally; temperature differences use `ΔK`.
- Every registered tool has a `test_tool_<name>` test.
- Respect the import-linter layers (`lint-imports`).
- Colours come from `branding/theme.json`; do not hard-code hex in components.
- `notebooks/` is frozen ahead of deprecation: do not add or edit notebooks.
- Never reproduce copyrighted code tables (ASME etc.); cite clause numbers instead.

## Releases (maintainers)

1. Bump `__version__` in `src/engtoolkit/__init__.py`.
2. In `CHANGELOG.md`, move the `[Unreleased]` entries under a new `[X.Y.Z] - date` heading and
   update the link references at the bottom.
3. Merge to `main`.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. The Release workflow checks the tag
   against `__version__`, builds the wheel and sdist, and publishes the GitHub release.
