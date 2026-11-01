import { BookOpen, Calculator, Check, FileDown, Link2, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ChartView } from "../components/ChartView";
import { ResultsView } from "../components/ResultsView";
import { ToolForm, type FieldErrors } from "../components/ToolForm";
import { Badge, cn, SECTION_META, Spinner } from "../components/ui";
import { useEngine } from "../lib/engine";
import { inputsNeedFluidLibrary } from "../lib/fluids";
import { usePrefs } from "../lib/prefs";
import { download, markdownReport } from "../lib/report";
import { defaultValues, fieldsFromSchema } from "../lib/schema";
import type { RunResponse } from "../lib/types";
import { decodeInputs, encodeInputs } from "../lib/urlState";
import { STRUCTURAL_PAGE_TOOLS, StructuralRoute } from "./StructuralPage";

export function ToolPage() {
  const { toolId = "" } = useParams();
  // tools with a dedicated page open it instead of the generic form
  if (STRUCTURAL_PAGE_TOOLS.has(toolId)) return <StructuralRoute />;
  return <GenericToolPage toolId={toolId} />;
}

function GenericToolPage({ toolId }: { toolId: string }) {
  const [params, setParams] = useSearchParams();
  const { schema, progress, run } = useEngine();
  const { units } = usePrefs();
  const tool = schema?.tools.find((t) => t.id === toolId);

  const fields = useMemo(() => (tool ? fieldsFromSchema(tool.inputs) : []), [tool]);
  const defaults = useMemo(() => defaultValues(fields), [fields]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [valuesFor, setValuesFor] = useState<string | null>(null); // tool the current values belong to
  const [response, setResponse] = useState<RunResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const autoRan = useRef<string | null>(null);

  // new tool (or a shared link): start from defaults plus any inputs in the URL
  useEffect(() => {
    setValues({ ...defaults, ...decodeInputs(params.get("i")) });
    setValuesFor(tool ? toolId : null);
    setResponse(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolId, defaults]);

  const calculate = async (inputs = values) => {
    if (!tool) return;
    setBusy(true);
    const encoded = encodeInputs(inputs, defaults);
    setParams(encoded ? { i: encoded } : {}, { replace: true });
    const res = await run(tool.id, inputs);
    setResponse(res);
    setBusy(false);
  };

  // shared links calculate automatically once Python is ready
  useEffect(() => {
    const link = params.get("i");
    if (tool && link && progress.stage === "ready" && valuesFor === tool.id && autoRan.current !== `${tool.id}?${link}`) {
      autoRan.current = `${tool.id}?${link}`;
      void calculate(values);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, progress.stage, valuesFor]);

  if (!schema) {
    return <div className="flex items-center gap-2 text-muted"><Spinner /> Loading tools…</div>;
  }
  if (!tool) {
    return (
      <div className="card p-6">
        <p className="mb-2 font-semibold">Tool not found</p>
        <Link className="text-primary underline" to="/">Back to all tools</Link>
      </div>
    );
  }

  const meta = SECTION_META[tool.section];
  const Icon = meta?.icon;
  const errors: FieldErrors = {};
  if (response && !response.ok && response.error.fields) {
    for (const f of response.error.fields) errors[f.loc.join(".")] = f.msg;
  }
  const ready = progress.stage === "ready";
  const heos = inputsNeedFluidLibrary(values);

  const copyLink = async () => {
    const encoded = encodeInputs(values, defaults);
    const url = `${location.origin}${location.pathname}#/tool/${tool.id}${encoded ? `?i=${encoded}` : ""}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("Copy this link", url);
    }
  };

  const exportReport = () => {
    if (!response?.ok) return;
    const encoded = encodeInputs(values, defaults);
    const link = `${location.origin}${location.pathname}#/tool/${tool.id}${encoded ? `?i=${encoded}` : ""}`;
    const md = markdownReport({ tool, fields, values, results: response.result.fields, system: units, version: schema.version, link });
    download(`${tool.id}.md`, md, "text/markdown");
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
          {Icon && <Icon className={cn("h-4 w-4", meta.text)} />}
          <span>{schema.sections[tool.section]}</span>
          {tool.custom_page && <Badge>Dedicated page coming in a later release</Badge>}
        </div>
        <h1 className="text-2xl font-bold tracking-tight">{tool.name}</h1>
        <p className="max-w-3xl text-muted">{tool.description}</p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <section className="card p-5">
          <h2 className="mb-4 text-sm font-semibold">Inputs</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void calculate();
            }}
          >
            <ToolForm fields={fields} values={values} onChange={setValues} errors={errors} />
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button type="submit" className="btn-primary" disabled={busy} data-testid="calculate">
                {busy ? <Spinner /> : <Calculator className="h-4 w-4" />}
                {busy ? (ready ? "Calculating…" : "Waiting for Python…") : "Calculate"}
              </button>
              <button type="button" className="btn-ghost" onClick={() => { setValues(defaults); setResponse(null); setParams({}, { replace: true }); }}>
                <RotateCcw className="h-4 w-4" /> Reset
              </button>
              <button type="button" className="btn-ghost" onClick={copyLink}>
                {copied ? <Check className="h-4 w-4 text-ok" /> : <Link2 className="h-4 w-4" />} {copied ? "Copied" : "Copy link"}
              </button>
            </div>
            {!ready && progress.stage !== "error" && (
              <p className="mt-3 text-xs text-muted">Python is loading in the background ({progress.percent}%). You can fill in the form meanwhile.</p>
            )}
            {busy && heos && <p className="mt-3 text-xs text-warn">Loading CoolProp's fluid library for this fluid (about a minute the first time)…</p>}
          </form>
        </section>

        <section className="card p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Results</h2>
            {response?.ok && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">{response.elapsed_ms} ms</span>
                <button className="btn-ghost text-xs" onClick={exportReport}>
                  <FileDown className="h-3.5 w-3.5" /> Report
                </button>
              </div>
            )}
          </div>
          {!response && <p className="text-sm text-muted">Set the inputs and press Calculate.</p>}
          {response && !response.ok && (
            <div className="flex gap-2 rounded-xl border border-fail/30 bg-fail/5 p-3 text-sm text-fail" data-testid="run-error">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{response.error.message}</span>
            </div>
          )}
          {response?.ok && <ResultsView fields={response.result.fields} toolId={tool.id} />}
        </section>
      </div>

      {response?.ok && response.charts.length > 0 && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {response.charts.map((c, i, all) => (
            <div key={c.id} className={cn("card p-3", all.length % 2 === 1 && i === all.length - 1 && "lg:col-span-2")}>
              <ChartView chart={c} />
            </div>
          ))}
        </section>
      )}

      <footer className="flex items-start gap-2 text-xs text-muted">
        <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span><span className="font-medium">Reference:</span> {tool.reference}</span>
      </footer>
    </div>
  );
}
