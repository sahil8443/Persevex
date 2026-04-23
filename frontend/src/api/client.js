import axios from "axios";

/**
 * Use same-origin in dev (Vite proxy) or VITE_API_URL in production builds.
 */
const baseURL = import.meta.env.VITE_API_URL || "";

export const api = axios.create({
  baseURL,
  headers: { Accept: "application/json" },
});

export async function uploadInvoice(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/upload-invoice", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchInvoices() {
  const { data } = await api.get("/invoices");
  return data;
}

export async function fetchInvoice(id) {
  const { data } = await api.get(`/invoice/${id}`);
  return data;
}

export async function fetchAnalytics() {
  const { data } = await api.get("/analytics");
  return data;
}

export async function exportDataset() {
  const response = await api.get("/export-dataset", {
    responseType: "blob",
  });
  // Trigger browser download
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "invoice_dataset.csv");
  document.body.appendChild(link);
  link.click();
  link.parentNode.removeChild(link);
  window.URL.revokeObjectURL(url);
}
