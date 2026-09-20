import { useState, useEffect } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Toaster } from "react-hot-toast";
import UploadPanel from "./components/UploadPanel";
import ChatPanel from "./components/ChatPanel";
import AnswerCard from "./components/AnswerCard";
import AnomalySummary from "./components/AnomalySummary";
import AuditHistory from "./components/AuditHistory";
import Login from "./pages/Login";
import { getSessionUser, clearSessionUser } from "./services/auth";
import api from "./services/api";

const CLOUD_BADGES = [
  "Amazon Bedrock (Claude / Nova)",
  "Strands Agents SDK",
  "Amazon S3 Durability",
  "Amazon DynamoDB Runs",
  "Deterministic Pandas Engine",
];

function DashboardPage({ onUploadComplete, onSelectPastRun, currentRunId }) {
  const [datasets, setDatasets] = useState([]);

  useEffect(() => {
    api.get("/datasets")
      .then((res) => setDatasets(res.data?.datasets || []))
      .catch((err) => console.error("Could not fetch user datasets", err));
  }, []);

  return (
    <div className="space-y-8 pb-12">
      {/* Hero section */}
      <section className="relative overflow-hidden rounded-3xl border border-slate-200 bg-linear-to-br from-cyan-50 via-white to-emerald-50 px-6 py-10 md:px-10 md:py-14 shadow-sm">
        <div className="relative max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300 bg-cyan-100/60 px-3 py-1 text-xs font-semibold text-cyan-800 mb-3">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            AuditIQ Cloud on AWS
          </div>
          <h1 className="font-display text-3xl md:text-4xl leading-tight text-slate-900">
            Evidence-backed AI financial audit investigation on AWS.
          </h1>
          <p className="text-base text-slate-600 mt-3 max-w-2xl leading-relaxed">
            Upload transaction datasets to Amazon S3, automatically detect policy anomalies,
            investigate financial questions with Strands Agent & Amazon Bedrock, and receive verifiable
            audit findings with trust, provenance, and full reproducibility.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {CLOUD_BADGES.map((b) => (
              <span
                key={b}
                className="inline-flex items-center rounded-md bg-white/80 border border-slate-200 px-2.5 py-1 text-xs text-slate-700 font-mono"
              >
                {b}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Main Upload / Datasets Grid */}
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] items-start">
        <div className="space-y-6">
          <UploadPanel onUploadComplete={onUploadComplete} />

          {datasets.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800 mb-3">
                Persistent S3 Datasets ({datasets.length})
              </h3>
              <div className="space-y-2">
                {datasets.map((ds) => (
                  <div
                    key={ds.dataset_id}
                    onClick={() => onUploadComplete && onUploadComplete(ds)}
                    className="p-3 rounded-xl border border-slate-100 hover:border-cyan-200 hover:bg-cyan-50/50 cursor-pointer transition-all flex items-center justify-between"
                  >
                    <div>
                      <p className="text-xs font-semibold text-slate-800">
                        {ds.file_name || "transactions.csv"}
                      </p>
                      <p className="text-[11px] text-slate-500 font-mono">
                        ID: {ds.dataset_id} • {ds.row_count || 0} rows
                      </p>
                    </div>
                    <span className="text-xs text-cyan-700 font-semibold hover:underline">
                      Load Dataset →
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <AuditHistory onSelectRun={onSelectPastRun} currentRunId={currentRunId} />
        </div>
      </div>
    </div>
  );
}

function AnalysisPage({
  dataset,
  anomalies,
  answer,
  setAnswer,
  loading,
  setLoading,
  chatSeed,
  onInvestigate,
  onSelectPastRun,
}) {
  return (
    <div className="space-y-4">
      {/* Session Header Card */}
      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-[0.14em] text-cyan-700 font-semibold">
              Audit Workspace
            </span>
            <span className="text-[10px] rounded bg-emerald-50 border border-emerald-200 text-emerald-700 px-2 py-0.5 font-mono">
              AWS Persistent
            </span>
          </div>
          <p className="text-xs text-slate-700 mt-1">
            Dataset: <span className="font-semibold">{dataset.file_name || "transactions.csv"}</span> ({dataset.rows || dataset.row_count || 0} transactions, {dataset.columns?.length || 0} columns)
          </p>
          {dataset.dataset_hash && (
            <p className="text-[10px] text-slate-400 font-mono mt-0.5 truncate max-w-md">
              Hash: {dataset.dataset_hash}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 px-3 py-1 font-medium">
            ● Active Session
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <AnomalySummary
            anomalies={anomalies}
            datasetInfo={dataset}
            onInvestigate={onInvestigate}
          />
          <ChatPanel
            datasetId={dataset.dataset_id}
            setAnswer={setAnswer}
            loading={loading}
            setLoading={setLoading}
            answer={answer}
            externalQuery={chatSeed}
          />
          <AuditHistory onSelectRun={onSelectPastRun} currentRunId={answer?.run_id} />
        </div>
        <div className="lg:sticky lg:top-6 self-start">
          <AnswerCard answer={answer} loading={loading} setAnswer={setAnswer} />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentUser, setCurrentUser] = useState(getSessionUser());

  const [dataset, setDataset] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [chatSeed, setChatSeed] = useState({ query: "", nonce: 0 });

  const handleInvestigate = (query) => {
    if (!query) return;
    setChatSeed({ query, nonce: Date.now() });
  };

  const handleUploadComplete = (uploadPayload) => {
    setDataset(uploadPayload);
    setAnomalies(uploadPayload?.anomalies || []);
    setAnswer(null);
    setLoading(false);
    setChatSeed({ query: "", nonce: Date.now() });
    navigate("/analysis");
  };

  const handleSelectPastRun = (run) => {
    if (!run) return;
    const details = run.details || {};
    const resPayload = details.result || {};

    const rehydratedAnswer = {
      run_id: run.run_id,
      query: run.query,
      dataset_id: run.dataset_id,
      dataset_hash: run.dataset_hash,
      replay_id: run.replay_id,
      execution_mode: run.execution_mode,
      narrative: run.finding || resPayload.narrative,
      logic_explanation: details.result?.logic_explanation || "",
      confidence: run.confidence || "high",
      confidence_reason: run.confidence_reason || "",
      trust: {
        score: run.trust_score || 85,
        level: run.trust_level || "HIGH",
      },
      narrative_grounding: {
        status: run.grounding_status || "pass",
      },
      consensus: {
        status: run.consensus_status || "high",
      },
      row_count: run.evidence_count || 0,
      result_records: resPayload.evidence_sample || [],
      columns: resPayload.columns || [],
      agent_trace: details.agent_trace || [],
      reproducibility: {
        replay_id: run.replay_id,
        query_hash: run.query_hash,
        plan_hash: run.plan_hash,
        generated_at: run.created_at,
      },
    };

    setAnswer(rehydratedAnswer);

    if (!dataset || dataset.dataset_id !== run.dataset_id) {
      setDataset({
        dataset_id: run.dataset_id,
        dataset_hash: run.dataset_hash,
        rows: run.evidence_count || 0,
        file_name: "reloaded_dataset.csv",
        columns: resPayload.columns || [],
      });
    }

    navigate("/analysis");
  };

  const handleNewUpload = () => {
    setDataset(null);
    setAnomalies([]);
    setAnswer(null);
    setLoading(false);
    setChatSeed({ query: "", nonce: Date.now() });
    navigate("/");
  };

  const handleLogout = () => {
    clearSessionUser();
    setCurrentUser({ isAuthenticated: false });
    setDataset(null);
    setAnswer(null);
    navigate("/");
  };

  const onAnalysisRoute = location.pathname.startsWith("/analysis");

  // Authentication Guard: render Login screen if not authenticated
  if (!currentUser.isAuthenticated) {
    return (
      <div className="min-h-screen text-slate-900 page-shell-gradient">
        <Toaster position="top-right" />
        <Login onLoginSuccess={(u) => setCurrentUser(u?.isAuthenticated ? u : getSessionUser())} />
      </div>
    );
  }

  return (
    <div className="min-h-screen text-slate-900 relative overflow-x-hidden page-shell-gradient">
      <Toaster position="top-right" />
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur px-5 md:px-8 py-3.5 flex flex-wrap items-center justify-between gap-3 shadow-2xs">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-cyan-600 to-emerald-600 flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
              <span className="text-white font-black text-base">A</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-display text-lg font-bold text-slate-900 leading-tight">
                  AuditIQ Cloud
                </h1>
                <span className="text-[10px] rounded-full bg-cyan-100 text-cyan-800 font-bold px-2 py-0.5 border border-cyan-200">
                  AWS Native
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Evidence-backed AI Financial Audit Investigation
              </p>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {/* User Role Badge */}
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="font-medium">{currentUser.username}</span>
            <span className="text-[10px] uppercase font-bold text-cyan-700 bg-cyan-50 px-1.5 py-0.5 rounded border border-cyan-200">
              {currentUser.role}
            </span>
          </div>

          <Link
            to="/"
            className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
              !onAnalysisRoute ? "bg-cyan-100/70 text-cyan-800" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Dashboard
          </Link>

          {dataset && (
            <Link
              to="/analysis"
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
                onAnalysisRoute ? "bg-cyan-100/70 text-cyan-800" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Workspace
            </Link>
          )}

          {onAnalysisRoute && (
            <button
              onClick={handleNewUpload}
              className="text-xs rounded-full border border-slate-300 px-3 py-1 text-slate-700 hover:bg-slate-100 transition-colors"
            >
              + New Upload
            </button>
          )}

          {/* Cognito Sign Out Button */}
          <button
            onClick={handleLogout}
            className="text-xs text-slate-500 hover:text-rose-600 font-medium px-2.5 py-1 rounded-lg border border-transparent hover:border-rose-200 hover:bg-rose-50 transition-all"
            title="Sign out of Amazon Cognito"
          >
            Sign Out
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8">
        <Routes>
          <Route
            path="/"
            element={
              <DashboardPage
                onUploadComplete={handleUploadComplete}
                onSelectPastRun={handleSelectPastRun}
                currentRunId={answer?.run_id}
              />
            }
          />
          <Route
            path="/analysis"
            element={
              dataset ? (
                <AnalysisPage
                  dataset={dataset}
                  anomalies={anomalies}
                  answer={answer}
                  setAnswer={setAnswer}
                  loading={loading}
                  setLoading={setLoading}
                  chatSeed={chatSeed}
                  onInvestigate={handleInvestigate}
                  onSelectPastRun={handleSelectPastRun}
                />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
