const severityColor = {
  high: "bg-red-50 border-red-200 text-red-800",
  medium: "bg-amber-50 border-amber-200 text-amber-800",
  low: "bg-blue-50 border-blue-200 text-blue-800",
};

const ANOMALY_QUERY_MAP = [
  {
    test: (label) => label.includes("duplicate") && (label.includes("gstin") || label.includes("vendor")),
    query: "Show vendors who share the same GSTIN",
  },
  {
    test: (label) => label.includes("round") && label.includes("invoice"),
    query: "Show round number invoices above 50000",
  },
  {
    test: (label) => label.includes("late") && label.includes("payment"),
    query: "Show late payment records",
  },
  {
    test: (label) => label.includes("purchase order") || label.includes("no po"),
    query: "Show transactions without purchase order",
  },
  {
    test: (label) => label.includes("disputed"),
    query: "Show all disputed invoices",
  },
  {
    test: (label) => label.includes("high value") || label.includes("outlier"),
    query: "Show high value transactions above 200000",
  },
  {
    test: (label) => label.includes("invoice number") || label.includes("duplicate invoice"),
    query: "Show duplicate invoice numbers",
  },
  {
    test: (label) => label.includes("spike") || label.includes("surge"),
    query: "Detect spending spikes exceeding statistical threshold",
  },
  {
    test: (label) => label.includes("concentration") || label.includes("vendor share"),
    query: "Show vendor concentration exceeding 12% spend",
  },
  {
    test: (label) => label.includes("split") || label.includes("threshold"),
    query: "Detect potential split payments near approval limits",
  },
];

function _queryForAnomalyType(type) {
  const normalized = String(type || "").toLowerCase();
  const matched = ANOMALY_QUERY_MAP.find((entry) => entry.test(normalized));
  return matched ? matched.query : "Show details for this anomaly and related records";
}

export default function AnomalySummary({ anomalies, datasetInfo, onInvestigate }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">Auto-detected anomalies</h3>
        <span className="text-xs text-gray-400">
          {datasetInfo.rows} transactions scanned
        </span>
      </div>
      {anomalies.length === 0 ? (
        <p className="text-sm text-gray-400">No anomalies detected.</p>
      ) : (
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <div
              key={i}
              className={`rounded-xl border px-4 py-3 text-sm ${severityColor[a.severity]}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">
                    {a.type} — {a.count} instance{a.count > 1 ? "s" : ""}
                  </div>
                  <div className="mt-1 text-xs opacity-80">{a.description}</div>
                </div>
                {onInvestigate && (
                  <button
                    onClick={() => onInvestigate(_queryForAnomalyType(a.type))}
                    className="text-xs bg-white/80 border border-current/25 rounded-lg px-2.5 py-1 hover:bg-white transition-colors whitespace-nowrap"
                  >
                    Investigate
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
