/// <reference lib="webworker" />
// Runs Python (Pyodide) off the main thread so the UI never freezes.
import * as Comlink from "comlink";
import type { EngineProgress, Manifest, RunResponse } from "../lib/types";

type Pyodide = {
  version: string;
  loadPackage: (names: string | string[]) => Promise<unknown>;
  pyimport: (name: string) => any;
  runPythonAsync: (code: string) => Promise<any>;
  globals: { get: (name: string) => any; set: (name: string, value: unknown) => void };
};

type Progress = (p: EngineProgress) => void;

let py: Pyodide | null = null;
let ready: Promise<string> | null = null;

// Python module name -> package to fetch the first time a tool imports it
const LAZY_PACKAGES: Record<string, string> = {
  scipy: "scipy", pandas: "pandas", matplotlib: "matplotlib", pint: "pint", PIL: "pillow", yaml: "pyyaml",
};

async function boot(baseUrl: string, report: Progress): Promise<string> {
  report({ stage: "loading-python", message: "Downloading Python (Pyodide)…", percent: 5 });
  const manifest: Manifest = await (await fetch(`${baseUrl}py/manifest.json`)).json();
  const url = `https://cdn.jsdelivr.net/pyodide/v${manifest.pyodide}/full/pyodide.mjs`;
  const mod = await import(/* @vite-ignore */ url);
  py = (await mod.loadPyodide()) as Pyodide;

  report({ stage: "loading-packages", message: "Loading NumPy, CoolProp and pydantic…", percent: 35 });
  await py.loadPackage(manifest.packages);

  report({ stage: "installing", message: "Installing the engineering toolkit…", percent: 70 });
  const micropip = py.pyimport("micropip");
  await micropip.install(new URL(`${baseUrl}py/${manifest.wheel}`, self.location.origin).href);

  report({ stage: "warming", message: "Preparing tools…", percent: 85 });
  await py.runPythonAsync(`
from engtoolkit.webapi import run_tool_json, schema_json
from engtoolkit.core import load_tools
load_tools()
`);
  report({ stage: "ready", message: "Ready", percent: 100 });
  return py.version;
}

async function runWithAutoload(code: string): Promise<any> {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      return await py!.runPythonAsync(code);
    } catch (err) {
      const match = String(err).match(/ModuleNotFoundError: No module named '([\w.]+)'/);
      const pkg = match && LAZY_PACKAGES[match[1].split(".")[0]];
      if (!pkg) throw err;
      try {
        await py!.loadPackage(pkg);
      } catch {
        await py!.pyimport("micropip").install(pkg);
      }
    }
  }
  throw new Error("Could not load the packages this tool needs");
}

const api = {
  init(baseUrl: string, onProgress: Progress): Promise<string> {
    if (!ready) {
      ready = boot(baseUrl, onProgress).catch((err) => {
        onProgress({ stage: "error", message: String(err), percent: 0 });
        ready = null;
        throw err;
      });
    }
    return ready;
  },

  async run(toolId: string, inputs: Record<string, unknown>): Promise<RunResponse> {
    if (!ready) return { ok: false, error: { kind: "engine", message: "Python is not loaded yet" } };
    await ready;
    try {
      py!.globals.set("__aa_tool", toolId);
      py!.globals.set("__aa_inputs", JSON.stringify(inputs));
      // run through the auto-loader so lazily imported packages are fetched on first use
      const out = await runWithAutoload("run_tool_json(__aa_tool, __aa_inputs)");
      return JSON.parse(out as string) as RunResponse;
    } catch (err) {
      return { ok: false, error: { kind: "engine", message: String(err) } };
    }
  },
};

export type EngineApi = typeof api;
Comlink.expose(api);
