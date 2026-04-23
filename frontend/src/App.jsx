import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Analytics from "./pages/Analytics.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import InvoiceDetail from "./pages/InvoiceDetail.jsx";
import Upload from "./pages/Upload.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Upload />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/invoice/:id" element={<InvoiceDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
