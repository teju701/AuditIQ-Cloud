import { useEffect, useState } from "react";
import api from "../services/api";
import toast from "react-hot-toast";
import TrustBadge from "./TrustBadge";
import EvidenceTable from "./EvidenceTable";
import AgentTrace from "./AgentTrace";

const EXECUTION_MODE_META = {
  locked_metric: {
    label: "Locked metric",
    classes: "bg-emerald-50 border-emerald-200 text-emerald-700",
  },
  safe_plan: {
    label: "Structured plan",
    classes: "bg-indigo-50 border-indigo-200 text-indigo-700",
  },
  clarification_required: {
    label: "Needs clarification",
    classes: "bg-amber-50 border-amber-200 text-amber-700",
  },
  planner_unavailable: {
    label: "Planner unavailable",
    classes: "bg-rose-50 border-rose-200 text-rose-700",
  },
  failed: {
    label: "Execution failed",
    classes: "bg-gray-100 border-gray-200 text-gray-700",
  },
};

const TAB_DEFS = [
  { key: "summary", label: "Summary" },
  { key: "why", label: "Why this is correct" },
  { key: "evidence", label: "Evidence" },
  { key: "trace", label: "Audit Trail" },
  { key: "repro", label: "Reproducibility" },
];

function _safeDate(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

function _confidencePhrase(confidence) {
  const normalized = String(confidence || "").toLowerCase();
  if (normalized === "high") return "Ready for immediate audit action";
  if (normalized === "medium") return "Review suggested before final action";
  if (normalized === "low") return "Needs analyst validation";
  return "Confidence not available";
}

function _toList(value) {
  return Array.isArray(value) ? value : [];
}

function _buildHighlightedColumns(answer) {
  const lineage = answer?.provenance?.lineage || {};
  const highlights = new Set();

  _toList(lineage.filters).forEach((item) => {
    if (item?.column) highlights.add(String(item.column));
  });
  _toList(lineage.group_by).forEach((column) => {
    if (column) highlights.add(String(column));
  });
  _toList(lineage.aggregations).forEach((item) => {
    if (item?.column) highlights.add(String(item.column));
  });
  _toList(lineage.sort).forEach((item) => {
    if (item?.column) highlights.add(String(item.column));
  });

  return Array.from(highlights);
}

function _lineageSummary(lineage) {
  if (!lineage || typeof lineage !== "object") return "No lineage details available.";

  const parts = [];

  if (lineage.locked_metric) {
    parts.push(`Locked metric ${lineage.locked_metric}`);
  }

  const filters = _toList(lineage.filters);
  if (filters.length > 0) {
    parts.push(`${filters.length} filter${filters.length > 1 ? "s" : ""}`);
  }

  const groups = _toList(lineage.group_by);
  if (groups.length > 0) {
    parts.push(`Grouped by ${groups.join(", ")}`);
  }

  const aggs = _toList(lineage.aggregations);
  if (aggs.length > 0) {
    parts.push(`${aggs.length} aggregation${aggs.length > 1 ? "s" : ""}`);
  }

  const sort = _toList(lineage.sort);
  if (sort.length > 0) {
    parts.push("Sorted output");
  }

  if (parts.length === 0) {
    return "No additional filters or transformations were required.";
  }

  return parts.join(" | ");
}

function ProvenanceStepper({ answer, modeLabel }) {
  const provenance = answer?.provenance || {};
  const lineage = provenance?.lineage || {};

  const steps = [
    {
      title: "Intent routed",
      detail: `System interpreted intent as ${answer?.plan_intent || provenance?.intent || "filter"}.`,
    },
    {
      title: "Execution path",
      detail: `${modeLabel} execution was selected for this query.`,
    },
    {
      title: "Evidence scope",
      detail: `${provenance?.input_rows ?? "-"} input rows -> ${provenance?.output_rows ?? "-"} output rows (${provenance?.evidence_coverage_pct ?? 0}% coverage).`,
    },
    {
      title: "Transformations",
      detail: _lineageSummary(lineage),
    },
    {
      title: "Result prepared",
      detail: `${answer?.row_count ?? 0} record${(answer?.row_count ?? 0) === 1 ? "" : "s"} returned to UI.`,
    },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white px-3 py-3">
      <p className="text-xs font-semibold text-gray-700 mb-3">Evidence provenance timeline</p>
      <ol className="space-y-3">
        {steps.map((step, idx) => (
          <li key={step.title} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 mt-1" />
              {idx < steps.length - 1 && <span className="w-px flex-1 bg-indigo-200 mt-1" />}
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-700">{step.title}</p>
              <p className="text-xs text-gray-600 mt-0.5">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function AnswerCard({ answer, loading, setAnswer }) {
  const [activeTab, setActiveTab] = useState("summary");
  const [pageLoading, setPageLoading] = useState(false);

  useEffect(() => {
    setActiveTab("summary");
  }, [answer?.replay_id, answer?.query]);

  if (loading)
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 flex items-center justify-center min-h-64">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Analyzing your data...</p>
        </div>
      </div>
    );

  if (!answer)
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 min-h-64 flex items-center justify-center">
        <p className="text-gray-400 text-sm text-center">
          Ask a question on the left to see the audit finding here.
        </p>
      </div>
    );

  const exportPDF = async () => {
    if (!answer?.dataset_id) {
      toast.error("Missing dataset session. Please run query again.");
      return;
    }

    try {
      const res = await api.post(
        "/export-pdf",
        {
          query: answer.query,
          dataset_id: answer.dataset_id,
          run_id: answer.run_id,
        },
        { responseType: "blob" },
      );

      const downloadUrlHeader = res.headers["x-download-url"];
      const s3KeyHeader = res.headers["x-s3-key"];

      const url = URL.createObjectURL(
        new Blob([res.data], { type: "application/pdf" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `AuditIQ_${answer.run_id || "finding"}.pdf`;
      a.click();

      if (s3KeyHeader) {
        toast.success(`PDF report stored in S3 (${s3KeyHeader})`);
      } else {
        toast.success("PDF exported successfully");
      }
    } catch {
      toast.error("Export failed. Please check connection.");
    }
  };

  const copyText = async (value, label) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(String(value));
      toast.success(`${label} copied`);
    } catch {
      toast.error(`Failed to copy ${label.toLowerCase()}`);
    }
  };

  const modeMeta = EXECUTION_MODE_META[answer.execution_mode] || {
    label: String(answer.execution_mode || "Unknown"),
    classes: "bg-gray-100 border-gray-200 text-gray-700",
  };

  const highlightedColumns = _buildHighlightedColumns(answer);

  const replayId = answer.replay_id || "";
  const generatedAt = answer.reproducibility?.generated_at;
  const queryHash = answer.reproducibility?.query_hash;
  const planHash = answer.reproducibility?.plan_hash;
  const datasetHash = answer.dataset_hash;
  const metricCandidates = answer.metric_resolution?.candidates || [];
  const confidencePhrase = _confidencePhrase(answer.confidence);
  const pagination = answer.pagination || {
    page: 1,
    page_size: Math.max(1, (answer.result_records || []).length || 50),
    total_rows: Number(answer.row_count || 0),
    total_pages: Number(answer.row_count || 0) > 0
      ? Math.max(1, Math.ceil(Number(answer.row_count || 0) / Math.max(1, (answer.result_records || []).length || 50)))
      : 1,
    has_prev: false,
    has_next: false,
  };

  const loadPage = async (targetPage) => {
    if (!setAnswer || pageLoading) return;
    if (!answer?.dataset_id || !answer?.query) return;

    const nextPage = Number(targetPage);
    if (!Number.isFinite(nextPage) || nextPage < 1) return;
    if (nextPage === Number(pagination.page || 1)) return;

    setPageLoading(true);
    try {
      const res = await api.post("/query", {
        dataset_id: answer.dataset_id,
        query: answer.query,
        page: nextPage,
        page_size: Number(pagination.page_size || 50),
      });

      setAnswer((prev) => ({
        ...prev,
        ...res.data,
        query: prev?.query || answer.query,
        dataset_id: prev?.dataset_id || answer.dataset_id,
      }));
    } catch {
      toast.error("Failed to load evidence page");
    } finally {
      setPageLoading(false);
    }
  };

  const tabItems = TAB_DEFS.map((tab) => {
    if (tab.key === "evidence") {
      return { ...tab, label: `Evidence (${answer.row_count ?? 0})` };
    }
    return tab;
  });

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-gray-800">Audit finding</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${modeMeta.classes}`}
            >
              {modeMeta.label}
            </span>
            {answer?.cache?.hit && (
              <span className="inline-flex items-center rounded-full border border-teal-200 bg-teal-50 text-teal-700 px-2.5 py-0.5 text-xs font-medium">
                Instant answer (cache)
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportPDF}
            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap"
          >
            Export PDF
          </button>
        </div>
      </div>

      {answer.execution_mode === "clarification_required" && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
          <p className="text-xs font-semibold text-amber-800">Clarification required</p>
          <p className="text-xs text-amber-700 mt-1">
            Multiple metric interpretations matched. Use the guided prompts in the left panel to choose one.
          </p>
          {metricCandidates.length > 0 && (
            <p className="text-xs text-amber-700 mt-2">
              Candidate metrics: {metricCandidates.join(", ")}
            </p>
          )}
        </div>
      )}

      {answer.execution_mode === "planner_unavailable" && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-3">
          <p className="text-xs font-semibold text-rose-800">Structured planner unavailable</p>
          <p className="text-xs text-rose-700 mt-1">
            This answer did not run a safe structured plan. Use a more specific prompt from the left panel.
          </p>
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="border-b border-gray-200 bg-gray-50 px-2 py-2 flex flex-wrap gap-1.5">
          {tabItems.map((tab) => {
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`text-xs rounded-lg px-3 py-1.5 transition-colors ${active
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-gray-600 border border-gray-200 hover:text-indigo-700 hover:border-indigo-200"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="p-3 space-y-3">
          {activeTab === "summary" && (
            <>
              {answer.query && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                  <p className="text-xs text-gray-500">You asked</p>
                  <p className="text-sm text-gray-700 mt-0.5">{answer.query}</p>
                </div>
              )}

              <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3">
                <p className="text-xs text-gray-500">System understood</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <span className="text-xs rounded-full bg-white border border-gray-200 px-2.5 py-0.5">
                    Intent: {answer.plan_intent || "filter"}
                  </span>
                  <span className="text-xs rounded-full bg-white border border-gray-200 px-2.5 py-0.5">
                    Confidence: {String(answer.confidence || "unknown")}
                  </span>
                  <span className="text-xs rounded-full bg-white border border-gray-200 px-2.5 py-0.5">
                    Rows: {answer.row_count ?? 0}
                  </span>
                  {answer.metric_used && (
                    <span className="text-xs rounded-full bg-white border border-gray-200 px-2.5 py-0.5">
                      Metric: {answer.metric_used}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-600 mt-2">{confidencePhrase}</p>
              </div>

              <div className="rounded-xl border border-gray-200 px-3 py-3">
                <p className="text-xs font-semibold text-gray-700 mb-1">Audit narrative</p>
                <p className="text-sm text-gray-700 leading-relaxed">{answer.narrative}</p>
              </div>
            </>
          )}

          {activeTab === "why" && (
            <>
              <TrustBadge
                trust={answer.trust}
                confidence={answer.confidence}
                narrativeGrounding={answer.narrative_grounding}
                consensus={answer.consensus}
                provenance={answer.provenance}
              />

              <ProvenanceStepper answer={answer} modeLabel={modeMeta.label} />

              {answer.logic_explanation && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3">
                  <p className="text-xs font-semibold text-gray-700">Execution logic</p>
                  <p className="text-xs text-gray-600 font-mono mt-1 wrap-break-word">{answer.logic_explanation}</p>
                </div>
              )}

              {(answer.consensus?.reason || answer.narrative_grounding?.status) && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3">
                  <p className="text-xs font-semibold text-gray-700 mb-1">Explainability checks</p>
                  <p className="text-xs text-gray-600">
                    Grounding status: {answer.narrative_grounding?.status || "unknown"}
                  </p>
                  {answer.consensus?.reason && (
                    <p className="text-xs text-gray-600 mt-1">Consensus note: {answer.consensus.reason}</p>
                  )}
                </div>
              )}
            </>
          )}

          {activeTab === "evidence" && (
            <EvidenceTable
              records={answer.result_records}
              columns={answer.columns}
              rowCount={answer.row_count}
              highlightedColumns={highlightedColumns}
              pagination={pagination}
              onPageChange={loadPage}
              pageLoading={pageLoading}
            />
          )}

          {activeTab === "trace" && (
            <AgentTrace trace={answer.agent_trace} />
          )}

          {activeTab === "repro" && (
            <div className="space-y-2">
              {(replayId || queryHash || planHash || datasetHash) && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-gray-700">Run fingerprint</p>
                    <div className="flex flex-wrap items-center gap-2">
                      {replayId && (
                        <button
                          onClick={() => copyText(replayId, "Replay ID")}
                          className="text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          Copy replay id
                        </button>
                      )}
                      {queryHash && (
                        <button
                          onClick={() => copyText(queryHash, "Query hash")}
                          className="text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          Copy query hash
                        </button>
                      )}
                      {planHash && (
                        <button
                          onClick={() => copyText(planHash, "Plan hash")}
                          className="text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          Copy plan hash
                        </button>
                      )}
                    </div>
                  </div>

                  {replayId && <p className="text-xs text-gray-600 mt-1 font-mono break-all">Replay ID: {replayId}</p>}
                  {datasetHash && <p className="text-xs text-gray-600 mt-1 font-mono break-all">Dataset hash: {datasetHash}</p>}
                  {queryHash && <p className="text-xs text-gray-600 mt-1 font-mono break-all">Query hash: {queryHash}</p>}
                  {planHash && <p className="text-xs text-gray-600 mt-1 font-mono break-all">Plan hash: {planHash}</p>}
                  <p className="text-xs text-gray-600 mt-1">Generated: {_safeDate(generatedAt)}</p>
                </div>
              )}

              <div className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-3">
                <p className="text-xs font-semibold text-gray-700 mb-1">Execution metadata</p>
                <p className="text-xs text-gray-600">Cache hit: {answer?.cache?.hit ? "true" : "false"}</p>
                <p className="text-xs text-gray-600 mt-1">Execution mode: {answer.execution_mode || "unknown"}</p>
                <p className="text-xs text-gray-600 mt-1">Rows returned: {answer.row_count ?? 0}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
