import { CheckCircle2, TriangleAlert } from "lucide-react";
import { useEngine } from "../lib/engine";
import { cn, Spinner } from "./ui";

export function EngineStatus({ compact = false }: { compact?: boolean }) {
  const { progress } = useEngine();
  const ready = progress.stage === "ready";
  const failed = progress.stage === "error";
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-full border px-3 py-1 text-xs",
        ready ? "border-ok/30 text-ok" : failed ? "border-fail/30 text-fail" : compact ? "border-white/15 text-white/70" : "border-border text-muted",
      )}
      title={progress.message}
      data-testid="engine-status"
      data-stage={progress.stage}
    >
      {ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : failed ? <TriangleAlert className="h-3.5 w-3.5" /> : <Spinner className="h-3.5 w-3.5" />}
      {ready ? "Python ready" : failed ? "Python failed to load" : compact ? `${progress.percent}%` : progress.message}
      {!ready && !failed && !compact && (
        <span className="h-1 w-16 overflow-hidden rounded-full bg-border">
          <span className="block h-full brand-gradient transition-all" style={{ width: `${progress.percent}%` }} />
        </span>
      )}
    </div>
  );
}
