import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadInvoice } from "../api/client";

function fmtBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function Upload() {
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [lastFile, setLastFile] = useState(null);
  const navigate = useNavigate();

  const onFile = useCallback(
    async (file) => {
      if (!file) return;
      setLastFile({ name: file.name, size: file.size, type: file.type });
      setError("");
      setResult(null);
      setLoading(true);
      try {
        const data = await uploadInvoice(file);
        console.log("Upload successful, setting result:", data);
        setResult(data);
      } catch (e) {
        console.error("Upload error:", e);
        const errorMsg = e.response?.data?.detail || e.message || "Upload failed";
        setError(errorMsg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  return (
    <div className="space-y-8">
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7">
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Upload an invoice
          </h1>
          <p className="text-slate-600 dark:text-slate-300 mt-2 leading-relaxed">
            Drag & drop a scan to extract fields (OCR), validate totals/dates, and flag anomalies
            using an Isolation Forest model.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <span className="badge-neutral">PNG / JPG</span>
            <span className="badge-neutral">Preprocess + OCR</span>
            <span className="badge-neutral">Rules + ML scoring</span>
          </div>
        </div>
        <div className="lg:col-span-5 card-solid">
          <div className="card-body">
            <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Tips</div>
            <ul className="mt-2 text-sm text-slate-600 dark:text-slate-300 space-y-1.5">
              <li>
                For best OCR, use clear scans (300+ DPI) and avoid heavy shadows.
              </li>
              <li>
                You can test quickly with dataset images under{" "}
                <span className="kbd">backend/data/batch_*</span>.
              </li>
              <li>
                Keyboard: press <span className="kbd">Tab</span> to focus the upload button.
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div className="card-solid overflow-hidden">
        <div className="card-body">
          <div
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                document.getElementById("file")?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-10 md:p-12 text-center transition ${
              dragOver
                ? "border-accent bg-gradient-to-b from-accent-soft/70 to-white dark:from-accent/20 dark:to-slate-950/30"
                : "border-slate-300 dark:border-slate-700 bg-gradient-to-b from-white to-slate-50 dark:from-slate-950/40 dark:to-slate-950/10"
            }`}
          >
            <div className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-gradient-to-br from-accent/20 to-violet-600/10 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-28 -right-28 h-80 w-80 rounded-full bg-gradient-to-br from-teal-600/10 to-accent/10 blur-3xl" />
            <div className="mx-auto max-w-lg">
              <div className="mx-auto h-12 w-12 rounded-2xl bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 grid place-items-center shadow-sm">
                <span className="text-lg font-black">↑</span>
              </div>
              <div className="mt-4 text-slate-900 dark:text-slate-100 font-semibold text-lg">
                Drop your invoice here
              </div>
              <div className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                or choose a file from your computer
              </div>

              <div className="mt-6 flex items-center justify-center gap-2">
                <input
                  type="file"
                  accept="image/*,.pdf"
                  className="hidden"
                  id="file"
                  onChange={(e) => onFile(e.target.files?.[0])}
                />
                <label htmlFor="file" className={`btn-primary cursor-pointer ${loading ? "pointer-events-none" : ""}`}>
                  {loading ? "Processing…" : "Choose file"}
                </label>
                <button
                  type="button"
                  onClick={() => navigate("/dashboard")}
                  className="btn-secondary"
                  disabled={loading}
                >
                  View dashboard
                </button>
              </div>

              {lastFile && (
                <div className="mt-4 text-xs text-slate-500">
                  Selected: <span className="font-mono">{lastFile.name}</span>{" "}
                  {lastFile.size ? `(${fmtBytes(lastFile.size)})` : ""}
                </div>
              )}

              {error && (
                <div className="mt-5 text-left">
                  <div className="badge-bad">Upload failed</div>
                  <div className="mt-2 text-sm text-slate-700 bg-danger-soft/40 border border-red-200 rounded-xl p-3">
                    {typeof error === "string" ? error : JSON.stringify(error)}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {result && (
        <div className="grid lg:grid-cols-12 gap-6">
          <section className="lg:col-span-7 card-solid">
            <div className="card-header flex items-center justify-between gap-3">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">OCR preview</h2>
              <span className="text-xs text-slate-500 dark:text-slate-400">Raw text from OCR engine</span>
            </div>
            <div className="card-body">
              <pre className="text-xs bg-slate-50 dark:bg-slate-900 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-xl p-4 max-h-72 overflow-auto whitespace-pre-wrap leading-relaxed text-slate-800">
                {result.raw_ocr_text || "(empty)"}
              </pre>
            </div>
          </section>
          <section className="lg:col-span-5 card-solid">
            <div className="card-header">
              <h2 className="font-semibold text-slate-900 dark:text-slate-100">Extraction result</h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Parsed fields + validation + anomaly status.
              </p>
            </div>
            <div className="card-body space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Invoice #</div>
                  <div className="font-mono text-slate-900 dark:text-slate-100 mt-0.5">
                    {result.parsed?.invoice_number || "—"}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Date</div>
                  <div className="text-slate-900 dark:text-slate-100 mt-0.5">{result.parsed?.invoice_date || "—"}</div>
                </div>
                <div className="col-span-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Vendor</div>
                  <div className="text-slate-900 dark:text-slate-100 mt-0.5">{result.parsed?.vendor_name || "—"}</div>
                </div>
                <div className="col-span-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-xs text-slate-500 dark:text-slate-400">Total</div>
                  <div className="text-slate-900 dark:text-slate-100 mt-0.5 font-extrabold text-lg">
                    {result.parsed?.total_amount != null ? result.parsed.total_amount : "—"}
                  </div>
                </div>
              </div>

              <div>
                {result.is_anomaly ? (
                  <div className="badge-bad">Anomaly: {result.anomaly_reason}</div>
                ) : (
                  <div className="badge-ok">Normal</div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => navigate(`/invoice/${result.id}`)} className="btn-primary">
                  Open detail
                </button>
                <button type="button" onClick={() => navigate("/dashboard")} className="btn-secondary">
                  Dashboard
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
