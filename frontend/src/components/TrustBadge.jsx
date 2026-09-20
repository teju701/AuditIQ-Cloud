const levelTheme = {
  High: "bg-green-50 text-green-900 border-green-200",
  Medium: "bg-amber-50 text-amber-900 border-amber-200",
  Low: "bg-rose-50 text-rose-900 border-rose-200",
};

function _clampScore(value) {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function _confidenceTag(trustScore) {
  if (trustScore >= 80) return "Ready to act";
  if (trustScore >= 55) return "Review suggested";
  return "Needs analyst check";
}

function _confidenceToScore(confidence) {
  const normalized = String(confidence || "").toLowerCase();
  if (normalized === "high") return 92;
  if (normalized === "medium") return 68;
  if (normalized === "low") return 35;
  return 55;
}

function _groundingToScore(groundingStatus) {
  const normalized = String(groundingStatus || "").toLowerCase();
  if (normalized === "pass") return 92;
  if (normalized === "warning") return 66;
  if (normalized === "fail") return 28;
  return 55;
}

function _coverageToScore(coveragePct) {
  if (typeof coveragePct !== "number" || Number.isNaN(coveragePct)) return 55;
  if (coveragePct < 2) return 30;
  if (coveragePct < 8) return 58;
  if (coveragePct <= 70) return 88;
  if (coveragePct <= 90) return 70;
  return 55;
}

function _consensusToScore(consensus) {
  if (!consensus) return 60;

  if (consensus.enabled && typeof consensus.score === "number") {
    return _clampScore(consensus.score);
  }

  const status = String(consensus.status || "").toLowerCase();
  if (status === "high") return 90;
  if (status === "medium") return 65;
  if (status === "low") return 35;
  return 60;
}

function _factorTone(score) {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 55) return "bg-amber-500";
  return "bg-rose-500";
}

export default function TrustBadge({
  trust,
  confidence,
  narrativeGrounding,
  consensus,
  provenance,
}) {
  if (!trust) return null;

  const overallScore = _clampScore(Number(trust.score || 0));
  const confidenceTag = _confidenceTag(overallScore);
  const coveragePct = Number(provenance?.evidence_coverage_pct);

  const factors = [
    {
      label: "Model confidence",
      score: _confidenceToScore(confidence),
      note: String(confidence || "unknown"),
    },
    {
      label: "Narrative grounding",
      score: _groundingToScore(narrativeGrounding?.status),
      note: String(narrativeGrounding?.status || "unknown"),
    },
    {
      label: "Dual-run consensus",
      score: _consensusToScore(consensus),
      note: consensus?.enabled ? "enabled" : "single path",
    },
    {
      label: "Evidence coverage",
      score: _coverageToScore(coveragePct),
      note: Number.isFinite(coveragePct) ? `${coveragePct.toFixed(2)}%` : "unknown",
    },
  ];

  const panelTheme = levelTheme[trust.level] || "bg-gray-50 text-gray-900 border-gray-200";

  return (
    <div className={`rounded-xl border px-4 py-3 ${panelTheme}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-sm">Trust board: {trust.level}</span>
        <span className="text-xs font-mono">{overallScore}/100</span>
      </div>

      <div className="w-full bg-white/70 rounded-full h-2 mb-2">
        <div
          className="h-2 rounded-full bg-current opacity-65 transition-all"
          style={{ width: `${overallScore}%` }}
        />
      </div>

      <p className="text-xs font-semibold opacity-90 mb-3">Confidence signal: {confidenceTag}</p>

      <div className="space-y-2 mb-3">
        {factors.map((factor) => (
          <div key={factor.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-medium">{factor.label}</span>
              <span className="font-mono">{_clampScore(factor.score)}/100</span>
            </div>
            <div className="h-1.5 bg-white/80 rounded-full">
              <div
                className={`h-1.5 rounded-full transition-all ${_factorTone(_clampScore(factor.score))}`}
                style={{ width: `${_clampScore(factor.score)}%` }}
              />
            </div>
            <p className="text-[11px] mt-1 opacity-85">{factor.note}</p>
          </div>
        ))}
      </div>

      <div>
        <p className="text-xs font-semibold mb-1">Penalty reasons</p>
        <div className="flex flex-wrap gap-1.5">
          {(trust.reasons || ["No risk signals reported."]).map((reason, idx) => (
            <span
              key={`${idx}-${reason}`}
              className="text-[11px] rounded-full bg-white/80 border border-current/20 px-2.5 py-0.5"
            >
              {reason}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
