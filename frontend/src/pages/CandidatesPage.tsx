import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Candidate, ImportSummary, Page } from "../api";

export function CandidatesPage() {
  const [data, setData] = useState<Page<Candidate> | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [importing, setImporting] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    api.listCandidates(search, page).then(setData).catch((e) => setError(e.message));
  };

  useEffect(load, [search, page]);

  const onImport = async (file: File) => {
    setImporting(true);
    setError(null);
    setSummary(null);
    try {
      const result = await api.importCandidates(file);
      setSummary(result);
      setPage(1);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Candidates</h1>
        <p className="mt-1 text-sm text-slate-500">
          Import your candidate list (CSV or Excel, with <code className="rounded bg-slate-100 px-1">name, phone</code> required;
          <code className="rounded bg-slate-100 px-1">id, email, current_company</code> optional). Invalid rows are
          skipped and reported, valid rows are kept even if a file has some bad data.
        </p>
      </div>

      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6">
        <label className="flex cursor-pointer flex-col items-center gap-2 text-center">
          <span className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
            {importing ? "Importing…" : "Upload candidates (.csv or .xlsx)"}
          </span>
          <span className="text-xs text-slate-400">Supports large files — rows are validated and imported in batches</span>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xlsm"
            className="hidden"
            disabled={importing}
            onChange={(e) => e.target.files?.[0] && onImport(e.target.files[0])}
          />
        </label>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <span className="text-slate-600">Rows read: <b>{summary.total_rows}</b></span>
            <span className="text-emerald-700">Imported: <b>{summary.imported}</b></span>
            <span className="text-sky-700">Updated: <b>{summary.updated}</b></span>
            <span className="text-rose-700">Skipped: <b>{summary.skipped}</b></span>
          </div>
          {summary.errors.length > 0 && (
            <div className="mt-3 max-h-40 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              {summary.errors.map((e, i) => (
                <div key={i}>Row {e.row}: {e.reason}</div>
              ))}
              {summary.skipped > summary.errors.length && <div>…and {summary.skipped - summary.errors.length} more</div>}
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 p-4">
          <input
            className="w-72 rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-slate-400"
            placeholder="Search name, phone, email…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <span className="text-sm text-slate-500">{data?.total ?? 0} candidates in pool</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Phone</th>
              <th className="px-4 py-2">Email</th>
              <th className="px-4 py-2">Current Company</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium text-slate-800">{c.name}</td>
                <td className="px-4 py-2 text-slate-600">{c.phone}</td>
                <td className="px-4 py-2 text-slate-600">{c.email ?? "—"}</td>
                <td className="px-4 py-2 text-slate-600">{c.current_company ?? "—"}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                  No candidates yet. Upload a CSV to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-slate-100 p-3 text-sm">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded px-3 py-1 text-slate-600 disabled:opacity-30"
            >
              Previous
            </button>
            <span className="text-slate-500">
              Page {data.page} of {Math.ceil(data.total / data.page_size)}
            </span>
            <button
              disabled={page * data.page_size >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="rounded px-3 py-1 text-slate-600 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
