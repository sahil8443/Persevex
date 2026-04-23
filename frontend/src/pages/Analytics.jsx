import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchAnalytics, exportDataset } from "../api/client";

function StatCard({ label, value, sub }) {
  return (
    <div className="card-solid relative overflow-hidden">
      <div className="pointer-events-none absolute -top-10 -right-10 h-28 w-28 rounded-full bg-gradient-to-br from-accent/20 to-violet-600/10 dark:from-accent/25 dark:to-violet-600/20 blur-2xl" />
      <div className="card-body">
        <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
        <div className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 tabular-nums">
          {value}
        </div>
        {sub && <div className="mt-1 text-sm text-slate-600 dark:text-slate-300">{sub}</div>}
      </div>
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const d = await fetchAnalytics();
        console.log("Analytics data received:", d);
        if (!cancelled) setData(d);
      } catch (e) {
        console.error("Analytics fetch error:", e);
        if (!cancelled) setError(e.message || "Failed to load analytics");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const amountHistogram = useMemo(() => {
    if (!data?.amounts?.length) {
      console.log("No amounts data");
      return [];
    }
    const amounts = data.amounts.filter((a) => a != null && !Number.isNaN(a));
    console.log("Filtered amounts:", amounts);
    if (!amounts.length) return [];
    const min = Math.min(...amounts);
    const max = Math.max(...amounts);
    const bins = 8;
    const width = (max - min) / bins || 1;
    const counts = Array.from({ length: bins }, (_, i) => ({
      range: `${(min + i * width).toFixed(0)}–${(min + (i + 1) * width).toFixed(0)}`,
      count: 0,
    }));
    amounts.forEach((a) => {
      let idx = Math.floor((a - min) / width);
      if (idx >= bins) idx = bins - 1;
      if (idx < 0) idx = 0;
      counts[idx].count += 1;
    });
    console.log("Histogram data:", counts);
    return counts;
  }, [data]);

  const outlierPoints = useMemo(() => {
    if (!data?.outliers) return [];
    return data.outliers.map((o, i) => ({
      x: i + 1,
      y: o.amount ?? 0,
      name: o.vendor || `ID ${o.id}`,
      reason: o.reason,
    }));
  }, [data]);

  if (error)
    return (
      <div className="card-solid">
        <div className="card-body">
          <div className="badge-bad">Analytics error</div>
          <div className="mt-2 text-sm text-slate-700">{error}</div>
        </div>
      </div>
    );
  if (loading || !data) return <p className="text-slate-500 dark:text-slate-400">Loading…</p>;

  const vendorEntries = Object.entries(data.vendor_counts || {}).slice(0, 10);

  const handleExport = async () => {
    try {
      setDownloading(true);
      await exportDataset();
    } catch (e) {
      console.error("Export error:", e);
      setError(e.message || "Failed to export dataset");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">Analytics</h1>
          <p className="text-slate-600 dark:text-slate-300 mt-2">Distribution and outlier visualization.</p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={handleExport}
            disabled={downloading || !data}
            className="btn btn-primary"
            title="Download all processed invoices as CSV"
          >
            {downloading ? "Downloading…" : "📥 Download Dataset"}
          </button>
          <span className="badge-neutral">Realtime from API</span>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total invoices" value={data.total_invoices} />
        <StatCard
          label="Flagged anomalies"
          value={data.anomaly_count}
          sub={data.total_invoices ? `${Math.round((data.anomaly_count / data.total_invoices) * 100)}% of total` : ""}
        />
        <StatCard label="Vendors" value={Object.keys(data.vendor_counts || {}).length} />
        <StatCard label="Amounts captured" value={(data.amounts || []).length} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="card-solid">
          <div className="card-header">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Amount distribution</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Histogram of invoice totals.</p>
          </div>
          <div className="h-72">
            {amountHistogram.length === 0 ? (
              <p className="text-slate-500 dark:text-slate-400 text-sm p-4">No amount data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={amountHistogram} margin={{ top: 20, right: 30, left: 0, bottom: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.3)" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 12, fill: "rgba(148,163,184,0.8)" }}
                    interval={0}
                    angle={-45}
                    textAnchor="end"
                    height={100}
                  />
                  <YAxis tick={{ fontSize: 12, fill: "rgba(148,163,184,0.8)" }} allowDecimals={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "1px solid rgba(148,163,184,0.3)", borderRadius: "8px", color: "#e2e8f0" }}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="card-solid">
          <div className="card-header">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Top vendors</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Highest invoice volume.</p>
          </div>
          <div className="h-72">
            {vendorEntries.length === 0 ? (
              <p className="text-slate-500 dark:text-slate-400 text-sm p-4">No vendors yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={vendorEntries.map(([name, count]) => ({ name, count }))}
                  layout="vertical"
                  margin={{ top: 20, right: 30, left: 150, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.3)" />
                  <XAxis type="number" tick={{ fontSize: 12, fill: "rgba(148,163,184,0.8)" }} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11, fill: "rgba(148,163,184,0.8)" }} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "1px solid rgba(148,163,184,0.3)", borderRadius: "8px", color: "#e2e8f0" }}
                  />
                  <Bar dataKey="count" fill="#14b8a6" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>

      <section className="card-solid">
        <div className="card-header">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Outliers</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Flagged invoices plotted by amount.</p>
        </div>
        <div className="h-80">
          {outlierPoints.length === 0 ? (
            <p className="text-slate-500 dark:text-slate-400 text-sm p-4">No anomalies recorded.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.3)" />
                <XAxis 
                  type="number"
                  dataKey="x" 
                  name="Order"
                  tick={{ fontSize: 12, fill: "rgba(148,163,184,0.8)" }}
                />
                <YAxis 
                  type="number"
                  dataKey="y" 
                  name="Amount"
                  tick={{ fontSize: 12, fill: "rgba(148,163,184,0.8)" }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "1px solid rgba(148,163,184,0.3)", borderRadius: "8px", color: "#e2e8f0" }}
                  formatter={(value, name) => [value, name === "y" ? "Amount" : name]}
                  labelFormatter={(_, p) => p?.payload?.name}
                />
                <Scatter name="Outliers" data={outlierPoints} fill="#dc2626">
                  {outlierPoints.map((_, i) => (
                    <Cell key={i} fill="#dc2626" />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </div>
        <ul className="mt-4 text-sm text-slate-600 dark:text-slate-300 space-y-1">
          {data.outliers.map((o) => (
            <li key={o.id}>
              <span className="font-mono text-xs text-slate-500 dark:text-slate-400">#{o.id}</span> {o.vendor || "Unknown"} — <span className="text-red-600 dark:text-red-400 font-semibold">{o.reason}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
