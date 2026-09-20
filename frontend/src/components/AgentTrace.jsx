import React from "react";

export default function AgentTrace({ trace = [] }) {
  if (!trace || trace.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-xs text-slate-500">
        No agent trace events recorded for this run.
      </div>
    );
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case "completed":
        return (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-xs font-bold">
            ✓
          </span>
        );
      case "warning":
        return (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-xs font-bold">
            !
          </span>
        );
      case "failed":
        return (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-100 text-rose-600 text-xs font-bold">
            ✕
          </span>
        );
      default:
        return (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-100 text-cyan-600 text-xs font-bold">
            ●
          </span>
        );
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Agent Execution Milestones
        </h4>
        <span className="text-[11px] rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 font-mono">
          {trace.length} events
        </span>
      </div>

      <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
        {trace.map((event, idx) => (
          <div key={idx} className="flex items-start gap-3 p-3 text-xs hover:bg-slate-50/60 transition-colors">
            <div className="mt-0.5 shrink-0">{getStatusIcon(event.status)}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold text-slate-800">{event.step}</p>
                {event.timestamp && (
                  <span className="text-[10px] text-slate-400 font-mono">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-slate-600 leading-relaxed">{event.description}</p>
              {event.details && Object.keys(event.details).length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {Object.entries(event.details).map(([k, v]) => (
                    <span
                      key={k}
                      className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600 font-mono"
                    >
                      {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
