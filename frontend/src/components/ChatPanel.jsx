import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "../services/api";
import toast from "react-hot-toast";

const EXAMPLE_QUERIES = [
  "Show vendors who share the same GSTIN",
  "Show transactions without purchase order",
  "Show late payment records",
  "Show round number invoices above 50000",
  "Show all disputed invoices",
];

const INTENT_QUICK_ACTIONS = [
  {
    label: "Duplicate GSTIN",
    query: "Show vendors who share the same GSTIN",
  },
  {
    label: "No PO risk",
    query: "Show transactions without purchase order",
  },
  {
    label: "Late payment",
    query: "Show late payment records",
  },
  {
    label: "Disputed invoices",
    query: "Show all disputed invoices",
  },
];

const METRIC_RECOVERY_QUERIES = {
  duplicate_vendor: "Show vendors who share the same GSTIN",
  round_number_invoice: "Show round number invoices above 50000",
  late_payment: "Show late payment records",
  no_purchase_order: "Show transactions without purchase order",
  high_value_transaction: "Show high value transactions above 200000",
  disputed_invoice: "Show all disputed invoices by department",
};

function _titleCaseMetric(metricKey) {
  return String(metricKey || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

function _buildRecoveryPrompts(answer) {
  if (!answer) return [];

  if (answer.execution_mode === "clarification_required") {
    const candidates = answer.metric_resolution?.candidates || [];
    return candidates.map(
      (metricKey) =>
        METRIC_RECOVERY_QUERIES[metricKey] ||
        `Run ${_titleCaseMetric(metricKey)} analysis`,
    );
  }

  if (answer.execution_mode === "planner_unavailable") {
    return [
      "Show vendors who share the same GSTIN",
      "Show transactions without purchase order",
      "Show late payment records",
    ];
  }

  return [];
}

export default function ChatPanel({
  datasetId,
  setAnswer,
  loading,
  setLoading,
  answer,
  externalQuery,
}) {
  const [query, setQuery] = useState("");
  const queryRef = useRef("");

  const recoveryPrompts = useMemo(() => _buildRecoveryPrompts(answer), [answer]);

  const submit = useCallback(async (q) => {
    const finalQuery = (q || queryRef.current || "").trim();
    if (!finalQuery) return;
    if (!datasetId) {
      toast.error("No dataset session found. Please upload again.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/query", {
        query: finalQuery,
        dataset_id: datasetId,
      });
      setAnswer({ ...res.data, query: finalQuery, dataset_id: res.data.dataset_id || datasetId });
    } catch (e) {
      toast.error("Query failed — check if the backend is running");
    } finally {
      setLoading(false);
    }
  }, [datasetId, setAnswer, setLoading]);

  useEffect(() => {
    if (!externalQuery?.query || !externalQuery?.nonce) return;
    setQuery(externalQuery.query);
    queryRef.current = externalQuery.query;
    submit(externalQuery.query);
  }, [externalQuery, submit]);

  const runPreset = (presetQuery) => {
    setQuery(presetQuery);
    queryRef.current = presetQuery;
    submit(presetQuery);
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-800 mb-4">
        Ask a question about your data
      </h3>

      {answer?.execution_mode === "clarification_required" && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
          <p className="text-xs font-semibold text-amber-800">Clarification required</p>
          <p className="text-xs text-amber-700 mt-1">
            Multiple metric interpretations matched your question. Pick one prompt to continue.
          </p>
          {recoveryPrompts.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {recoveryPrompts.slice(0, 3).map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => runPreset(prompt)}
                  className="text-xs bg-white border border-amber-300 text-amber-800 rounded-full px-3 py-1 hover:bg-amber-100 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {answer?.execution_mode === "planner_unavailable" && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-3">
          <p className="text-xs font-semibold text-rose-800">Structured plan unavailable</p>
          <p className="text-xs text-rose-700 mt-1">
            We could not parse a reliable plan for this question. Try one of these focused prompts.
          </p>
          {recoveryPrompts.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {recoveryPrompts.slice(0, 3).map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => runPreset(prompt)}
                  className="text-xs bg-white border border-rose-300 text-rose-800 rounded-full px-3 py-1 hover:bg-rose-100 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <textarea
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          queryRef.current = e.target.value;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="e.g. Show all vendors with duplicate GSTIN..."
        rows={3}
        className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"
      />
      <button
        onClick={() => submit()}
        disabled={loading}
        className="mt-3 w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
      >
        {loading ? "Analyzing..." : "Run audit query"}
      </button>

      <div className="mt-4">
        <p className="text-xs text-gray-400 mb-2">Intent quick actions:</p>
        <div className="flex flex-wrap gap-2">
          {INTENT_QUICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              onClick={() => runPreset(action.query)}
              className="text-xs rounded-full border border-indigo-200 text-indigo-700 bg-indigo-50 px-3 py-1 hover:bg-indigo-100 transition-colors"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        <p className="text-xs text-gray-400 mb-2">Try an example:</p>
        <div className="space-y-1.5">
          {EXAMPLE_QUERIES.map((q, i) => (
            <button
              key={i}
              onClick={() => {
                runPreset(q);
              }}
              className="block w-full text-left text-xs text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded-lg px-3 py-1.5 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
