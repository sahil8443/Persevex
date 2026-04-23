import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchInvoices } from "../api/client";

function Badge({ ok, text }) {
  return ok ? (
    <span className="badge-ok">Normal</span>
  ) : (
    <span className="badge-bad">{text || "Anomaly"}</span>
  );
}

export default function Dashboard() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const data = await fetchInvoices();
        if (!cancelled) setRows(data);
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">Dashboard</h1>
          <p className="text-slate-600 dark:text-slate-300 mt-2">Latest uploads and fraud scores.</p>
        </div>
        <Link to="/" className="btn-primary">
          Upload invoice
        </Link>
      </div>

      {error && (
        <div className="card-solid">
          <div className="card-body">
            <div className="badge-bad">Could not load invoices</div>
            <div className="mt-2 text-sm text-slate-700">{error}</div>
          </div>
        </div>
      )}

      <div className="card-solid overflow-hidden">
        <div className="card-header flex items-center justify-between">
          <div>
            <div className="font-semibold text-slate-900">Invoices</div>
            <div className="text-xs text-slate-500 mt-0.5">
              {loading ? "Loading…" : `${rows.length} records`}
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50/70 dark:bg-slate-900/40 text-left text-slate-600 dark:text-slate-300">
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="px-5 py-3 font-semibold">Invoice No</th>
                <th className="px-5 py-3 font-semibold">Vendor</th>
                <th className="px-5 py-3 font-semibold">Amount</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-slate-500">
                    Loading invoices…
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center">
                    <div className="mx-auto max-w-md">
                      <div className="text-slate-900 font-semibold">No invoices yet</div>
                      <div className="text-slate-600 text-sm mt-1">
                        Upload an invoice to see extracted fields and anomaly scoring.
                      </div>
                      <div className="mt-4">
                        <Link to="/" className="btn-primary">
                          Upload your first invoice
                        </Link>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
              {!loading &&
                rows.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/70 dark:hover:bg-slate-900/40 transition"
                  >
                    <td className="px-5 py-4 font-mono text-xs text-slate-700 dark:text-slate-200">
                      {r.invoice_number || "—"}
                    </td>
                    <td className="px-5 py-4 text-slate-900 dark:text-slate-100">{r.vendor_name || "—"}</td>
                    <td className="px-5 py-4 text-slate-900 dark:text-slate-100 font-semibold tabular-nums">
                      {r.total_amount != null ? r.total_amount.toFixed(2) : "—"}
                    </td>
                    <td className="px-5 py-4">
                      <Badge ok={!r.is_anomaly} text={r.anomaly_reason ? `Anomaly: ${r.anomaly_reason}` : "Anomaly"} />
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link to={`/invoice/${r.id}`} className="btn-ghost">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
