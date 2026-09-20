import React, { useEffect, useState } from "react";
import api from "../services/api";

export default function AuditHistory({ onSelectRun, currentRunId }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      const res = await api.get("/audit-runs?limit=25");
      setRuns(res.data?.audit_runs || []);
      setError(null);
    } catch (err) {
      console.error("Failed to load audit history:", err);
      setError("Unable to load persistent audit investigations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  if (loading && runs.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-base font-semibold text-slate-800">
            Recent Audit Investigations
          </h3>
          <span className="text-xs text-slate-400">Syncing with DynamoDB...</span>
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-slate-100" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-base font-semibold text-slate-900">
            Recent Audit Investigations
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Persistent audit runs stored in DynamoDB & S3
          </p>
        </div>
        <button
          onClick={fetchRuns}
          className="text-xs text-cyan-700 hover:text-cyan-800 font-medium px-2 py-1 rounded hover:bg-cyan-50 transition-colors"
        >
          Refresh
        </button>
      </div>

      {error ? (
        <div className="p-4 rounded-xl bg-rose-50 text-rose-700 text-xs">{error}</div>
      ) : runs.length === 0 ? (
        <div className="text-center py-8 text-xs text-slate-400">
          No audit investigations recorded yet. Upload a dataset and ask your first audit question.
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {runs.map((run) => {
            const isSelected = currentRunId === run.run_id;
            const trustScore = run.trust_score || 0;
            const trustColor =
              trustScore >= 80
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : trustScore >= 60
                ? "text-amber-700 bg-amber-50 border-amber-200"
                : "text-rose-700 bg-rose-50 border-rose-200";

            return (
              <div
                key={run.run_id}
                onClick={() => onSelectRun && onSelectRun(run)}
                className={`py-3.5 px-2 -mx-2 rounded-xl transition-all cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-3 ${
                  isSelected ? "bg-cyan-50/70 border border-cyan-200" : "hover:bg-slate-50"
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] font-semibold text-slate-500">
                      {run.run_id}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {run.created_at ? new Date(run.created_at).toLocaleTimeString() : ""}
                    </span>
                    {run.execution_mode && (
                      <span className="text-[10px] rounded bg-slate-100 text-slate-600 px-1.5 py-0.5 font-mono">
                        {run.execution_mode}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-semibold text-slate-800 mt-1 line-clamp-1">
                    "{run.query}"
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">
                    {run.finding}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${trustColor}`}
                  >
                    Trust {trustScore}/100
                  </span>
                  <span
                    className={`rounded border px-2 py-0.5 text-[10px] uppercase font-bold ${
                      run.grounding_status === "pass"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-slate-200 bg-slate-50 text-slate-600"
                    }`}
                  >
                    {run.grounding_status === "pass" ? "Grounding PASS" : run.grounding_status || "Grounding"}
                  </span>
                  <button className="text-xs text-cyan-700 font-semibold hover:underline">
                    Reopen →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
