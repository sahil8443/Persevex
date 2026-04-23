import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchInvoice } from "../api/client";

function Flag({ label, bad }) {
  return bad ? <span className="badge-bad">{label}</span> : <span className="badge-ok">{label}</span>;
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const [inv, setInv] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const data = await fetchInvoice(id);
        if (!cancelled) setInv(data);
      } catch (e) {
        if (!cancelled) setError(e.response?.status === 404 ? "Not found" : e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <div className="card-solid">
        <div className="card-body">
          <div className="badge-bad">Error</div>
          <div className="mt-2 text-sm text-slate-700">{error}</div>
          <div className="mt-4">
            <Link to="/dashboard" className="btn-secondary">
              Back to dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }
  if (loading || !inv) return <p className="text-slate-500 dark:text-slate-400">Loading…</p>;

  const v = inv.validation || {};
  const lines = inv.parsed?.line_items || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Invoice <span className="font-mono text-slate-600 dark:text-slate-300">#{inv.id}</span>
          </h1>
          <p className="text-slate-600 dark:text-slate-300 mt-2">{inv.parsed?.vendor_name || "Unknown vendor"}</p>
        </div>
        <div className="flex items-center gap-2">
          {inv.is_anomaly ? (
            <span className="badge-bad">Anomaly: {inv.anomaly_reason}</span>
          ) : (
            <span className="badge-ok">Normal</span>
          )}
          <Link to="/dashboard" className="btn-secondary">
            ← Dashboard
          </Link>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <section
          className={`card-solid ${
            inv.is_anomaly ? "ring-1 ring-red-200 dark:ring-red-900/60 bg-danger-soft/20 dark:bg-red-950/20" : ""
          }`}
        >
          <div className="card-header">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Validation</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Rule checks and model signals.</p>
          </div>
          <div className="card-body">
            <div className="flex flex-wrap gap-2 mb-4">
              <Flag
                label={`Math: ${v.math_ok === false ? "fail" : v.math_ok ? "ok" : "n/a"}`}
                bad={v.math_ok === false}
              />
              <Flag
                label={`Date: ${v.date_ok === false ? "fail" : v.date_ok ? "ok" : "n/a"}`}
                bad={v.date_ok === false}
              />
            </div>
            {(v.errors?.length > 0 || v.warnings?.length > 0) && (
              <div className="space-y-3">
                {v.errors?.length > 0 && (
                  <div className="rounded-xl border border-red-200 dark:border-red-900/60 bg-danger-soft/30 dark:bg-red-950/20 p-3">
                    <div className="text-xs font-semibold text-danger uppercase tracking-wide">
                      Errors
                    </div>
                    <ul className="mt-2 text-sm text-slate-800 dark:text-slate-200 space-y-1">
                      {v.errors.map((e, i) => (
                        <li key={`e-${i}`}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {v.warnings?.length > 0 && (
                  <div className="rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 p-3">
                    <div className="text-xs font-semibold text-amber-800 uppercase tracking-wide">
                      Warnings
                    </div>
                    <ul className="mt-2 text-sm text-slate-800 dark:text-slate-200 space-y-1">
                      {v.warnings.map((w, i) => (
                        <li key={`w-${i}`}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {inv.anomaly_details && Object.keys(inv.anomaly_details).length > 0 && (
              <div className="mt-5">
                <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
                  Model / signals
                </div>
                <pre className="text-xs bg-slate-950/95 text-slate-100 rounded-xl p-4 overflow-auto max-h-48 border border-slate-800/30">
                  {JSON.stringify(inv.anomaly_details, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </section>

        <section className="card-solid">
          <div className="card-header">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Parsed fields</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Structured data extracted from OCR text.</p>
          </div>
          <div className="card-body">
            <dl className="grid grid-cols-1 gap-3 text-sm">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-100 dark:border-slate-800">
                <dt className="text-xs text-slate-500 dark:text-slate-400">Invoice number</dt>
                <dd className="font-mono text-slate-900 dark:text-slate-100 mt-0.5">
                  {inv.parsed?.invoice_number || "—"}
                </dd>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-100 dark:border-slate-800">
                <dt className="text-xs text-slate-500 dark:text-slate-400">Date</dt>
                <dd className="text-slate-900 dark:text-slate-100 mt-0.5">{inv.parsed?.invoice_date || "—"}</dd>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/40 border border-slate-100 dark:border-slate-800">
                <dt className="text-xs text-slate-500 dark:text-slate-400">Total</dt>
                <dd className="text-slate-900 dark:text-slate-100 mt-0.5 font-extrabold text-lg tabular-nums">
                  {inv.parsed?.total_amount != null ? inv.parsed.total_amount : "—"}
                </dd>
              </div>
            </dl>
          </div>
        </section>
      </div>

      <section className="card-solid overflow-hidden">
        <div className="card-header">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Line items</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50/70 dark:bg-slate-900/40 text-left text-slate-600 dark:text-slate-300">
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="px-5 py-3 font-semibold">Description</th>
                <th className="px-5 py-3 font-semibold">Qty</th>
                <th className="px-5 py-3 font-semibold">Price</th>
                <th className="px-5 py-3 font-semibold">Line total</th>
              </tr>
            </thead>
            <tbody>
              {lines.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-10 text-slate-500">
                    No line items parsed.
                  </td>
                </tr>
              )}
              {lines.map((li, idx) => (
                <tr key={idx} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/70 dark:hover:bg-slate-900/40 transition">
                  <td className="px-5 py-4 text-slate-900 dark:text-slate-100">{li.description}</td>
                  <td className="px-5 py-4 tabular-nums text-slate-700 dark:text-slate-200">{li.qty ?? "—"}</td>
                  <td className="px-5 py-4 tabular-nums text-slate-700 dark:text-slate-200">{li.price ?? "—"}</td>
                  <td className="px-5 py-4 tabular-nums text-slate-700 dark:text-slate-200">{li.line_total ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card-solid">
        <div className="card-header">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Raw OCR</h2>
        </div>
        <div className="card-body">
          <pre className="text-xs bg-slate-50 dark:bg-slate-900/40 border border-slate-100 dark:border-slate-800 rounded-xl p-4 max-h-72 overflow-auto whitespace-pre-wrap leading-relaxed">
            {inv.raw_ocr_text || "(empty)"}
          </pre>
        </div>
      </section>
    </div>
  );
}
