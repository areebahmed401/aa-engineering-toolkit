// React access to the Python engine (Pyodide in a Web Worker) and the static schema/choices.
import * as Comlink from "comlink";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { EngineApi } from "../worker/pyodide.worker";
import type { Choices, EngineProgress, RunResponse, Schema } from "./types";

const BASE = import.meta.env.BASE_URL;

type EngineState = {
  schema: Schema | null;
  choices: Choices | null;
  progress: EngineProgress;
  pythonVersion: string | null;
  run: (toolId: string, inputs: Record<string, unknown>) => Promise<RunResponse>;
};

const EngineContext = createContext<EngineState | null>(null);

export function EngineProvider({ children }: { children: ReactNode }) {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [choices, setChoices] = useState<Choices | null>(null);
  const [progress, setProgress] = useState<EngineProgress>({ stage: "idle", message: "Starting…", percent: 0 });
  const [pythonVersion, setPythonVersion] = useState<string | null>(null);
  const apiRef = useRef<Comlink.Remote<EngineApi> | null>(null);
  const readyRef = useRef<Promise<string> | null>(null);

  useEffect(() => {
    // schema and choices are static files, so forms render before Python has loaded
    fetch(`${BASE}py/schema.json`).then((r) => r.json()).then(setSchema).catch(() => setSchema(null));
    fetch(`${BASE}py/choices.json`).then((r) => r.json()).then(setChoices).catch(() => setChoices(null));

    const worker = new Worker(new URL("../worker/pyodide.worker.ts", import.meta.url), { type: "module" });
    const api = Comlink.wrap<EngineApi>(worker);
    apiRef.current = api;
    readyRef.current = api.init(BASE, Comlink.proxy(setProgress));
    readyRef.current.then(setPythonVersion).catch(() => undefined);
    return () => worker.terminate();
  }, []);

  const run = useCallback(async (toolId: string, inputs: Record<string, unknown>): Promise<RunResponse> => {
    if (!apiRef.current || !readyRef.current) {
      return { ok: false, error: { kind: "engine", message: "Python engine not started" } };
    }
    try {
      await readyRef.current;
    } catch (err) {
      return { ok: false, error: { kind: "engine", message: `Python failed to load: ${err}` } };
    }
    return apiRef.current.run(toolId, inputs);
  }, []);

  const value = useMemo(() => ({ schema, choices, progress, pythonVersion, run }), [schema, choices, progress, pythonVersion, run]);
  return <EngineContext.Provider value={value}>{children}</EngineContext.Provider>;
}

export function useEngine(): EngineState {
  const ctx = useContext(EngineContext);
  if (!ctx) throw new Error("useEngine must be used inside EngineProvider");
  return ctx;
}
