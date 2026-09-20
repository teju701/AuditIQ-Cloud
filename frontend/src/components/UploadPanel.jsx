import { useState } from "react";
import api from "../services/api";
import toast from "react-hot-toast";

const PROCESS_STAGES = {
  uploading: {
    label: "Uploading file",
    detail: "Securely sending file to analysis engine.",
    progress: 34,
  },
  profiling: {
    label: "Profiling dataset",
    detail: "Mapping fields and scanning anomaly signals.",
    progress: 72,
  },
  launching: {
    label: "Opening analysis workspace",
    detail: "Preparing chat and evidence panels.",
    progress: 100,
  },
};

export default function UploadPanel({ onUploadComplete }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [stage, setStage] = useState("uploading");
  const [selectedName, setSelectedName] = useState("");

  const handleFile = async (file) => {
    if (!file) return;
    setSelectedName(file.name || "dataset file");
    setUploading(true);
    setStage("uploading");

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await api.post("/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setStage("profiling");
      await new Promise((resolve) => setTimeout(resolve, 380));

      setStage("launching");
      await new Promise((resolve) => setTimeout(resolve, 320));

      toast.success(`Loaded ${res.data.rows} transactions`);
      onUploadComplete?.(res.data);
    } catch (e) {
      toast.error("Upload failed. Please check file format and backend status.");
      setStage("uploading");
      setUploading(false);
    } finally {
      if (!onUploadComplete) {
        setUploading(false);
      }
    }
  };

  const stageMeta = PROCESS_STAGES[stage] || PROCESS_STAGES.uploading;

  return (
    <div className="relative rounded-3xl border border-cyan-200 bg-white p-5 md:p-6 shadow-[0_25px_80px_-55px_rgba(13,148,136,0.8)] upload-focus-glow">
      <div className="absolute -inset-px rounded-3xl pointer-events-none border border-cyan-300/55" />

      <div className="relative mb-4">
        <h3 className="font-display text-2xl text-slate-900">Upload your transaction dataset</h3>
        <p className="text-sm text-slate-600 mt-1">CSV, XLSX, or XLS. Analysis starts automatically after upload.</p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files[0]);
        }}
        className={`relative border-2 border-dashed rounded-2xl p-8 md:p-10 text-center cursor-pointer transition-all duration-200 ${
          dragging
            ? "border-cyan-500 bg-cyan-50 scale-[1.01]"
            : "border-slate-300 bg-white hover:border-cyan-400 hover:bg-cyan-50/40"
        }`}
      >
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          id="file-input"
          onChange={(e) => handleFile(e.target.files[0])}
        />
        <label htmlFor="file-input" className="cursor-pointer block">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-linear-to-br from-cyan-500 to-emerald-500 text-white flex items-center justify-center text-xl shadow-sm">
            <span aria-hidden="true">+</span>
          </div>
          <p className="font-semibold text-slate-800 mt-4">
            Drop file here or click to browse
          </p>
          <p className="text-xs text-slate-500 mt-2">Supports .csv, .xlsx, .xls</p>
          {selectedName && (
            <p className="text-xs text-cyan-700 mt-2">Selected: {selectedName}</p>
          )}
        </label>
      </div>

      {uploading && (
        <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50/80 px-3 py-3">
          <div className="flex items-center justify-between text-xs">
            <p className="font-semibold text-cyan-800">{stageMeta.label}</p>
            <p className="font-mono text-cyan-700">{stageMeta.progress}%</p>
          </div>
          <div className="h-1.5 rounded-full bg-white mt-2">
            <div
              className="h-1.5 rounded-full bg-linear-to-r from-cyan-500 to-emerald-500 transition-all duration-300"
              style={{ width: `${stageMeta.progress}%` }}
            />
          </div>
          <p className="text-xs text-cyan-700 mt-2">{stageMeta.detail}</p>
        </div>
      )}

      <p className="text-xs text-slate-500 mt-4">Primary action: upload once, continue to analysis workspace.</p>
    </div>
  );
}
