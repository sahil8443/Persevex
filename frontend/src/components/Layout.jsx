import { Link, NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../theme/ThemeProvider.jsx";

const navCls = ({ isActive }) =>
  `px-3 py-2 rounded-xl text-sm font-semibold transition ${
    isActive
      ? "bg-accent text-white shadow-sm"
      : "text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white/70 dark:hover:bg-slate-900/60"
  }`;

export default function Layout() {
  const { isDark, toggle } = useTheme();
  return (
    <div className="app-shell flex flex-col">
      <header className="sticky top-0 z-20">
        <div className="bg-white/60 dark:bg-slate-950/50 backdrop-blur border-b border-slate-200/70 dark:border-slate-800">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <Link to="/" className="flex items-center gap-2">
              <div className="h-9 w-9 rounded-2xl bg-gradient-to-br from-accent-600 to-violet-600 shadow-sm ring-1 ring-white/40 dark:ring-white/10" />
              <div className="leading-tight">
                <div className="font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                  InvoiceGuard
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 -mt-0.5">
                  OCR • Validation • Anomaly ML
                </div>
              </div>
            </Link>
            <div className="flex items-center gap-2">
              <nav className="flex flex-wrap gap-1 p-1 rounded-2xl bg-white/50 dark:bg-slate-950/30 border border-slate-200/70 dark:border-slate-800">
              <NavLink to="/" end className={navCls}>
                Upload
              </NavLink>
              <NavLink to="/dashboard" className={navCls}>
                Dashboard
              </NavLink>
              <NavLink to="/analytics" className={navCls}>
                Analytics
              </NavLink>
              </nav>
              <button
                type="button"
                onClick={toggle}
                className="btn-secondary"
                aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
                title={isDark ? "Light mode" : "Dark mode"}
              >
                {isDark ? "Light" : "Dark"}
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-10">
        <Outlet />
      </main>
      <footer className="py-6 text-center text-xs text-slate-500">
        <span className="px-3 py-1.5 rounded-full bg-white/70 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 dark:text-slate-400">
          Tip: OCR uses Tesseract on the API machine.
        </span>
      </footer>
    </div>
  );
}
