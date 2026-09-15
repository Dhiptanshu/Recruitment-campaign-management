import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Campaign, ImportSummary, Page, ScreeningListItem } from "../api";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/Badge";

const FILTERS: { key: string; label: string; status?: string; recommendation?: string }[] = [
  { key: "all", label: "All" },
  { key: "shortlisted", label: "Shortlisted", status: "completed", recommendation: "shortlisted" },
  { key: "manual_review", label: "Manual Review", status: "completed", recommendation: "manual_review" },
  { key: "rejected", label: "Rejected", status: "completed", recommendation: "rejected" },
  { key: "pending", label: "Pending", status: "not_contacted" },
  { key: "failed", label: "Failed", status: "failed" },
];

export function CampaignDetailPage() {
  const { id } = useParams();
  const campaignId = Number(id);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [screenings, setScreenings] = useState<Page<ScreeningListItem> | null>(null);
  const [activeFilter, setActiveFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadCampaign = () => api.getCampaign(campaignId).then(setCampaign).catch((e) => setError(e.message));
  const loadScreenings = () => {
    const f = FILTERS.find((f) => f.key === activeFilter);
    api
      .listScreenings(campaignId, { status: f?.status, recommendation: f?.recommendation, search, page })
      .then(setScreenings)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    loadCampaign();
  }, [campaignId]);

  useEffect(() => {
    loadScreenings();
  }, [campaignId, activeFilter, search, page]);

  useEffect(() => {
    if (campaign?.status !== "running") return;
    const t = setInterval(() => {
      loadCampaign();
      loadScreenings();
    }, 2000);
    return () => clearInterval(t);
  }, [campaign?.status, activeFilter, search, page]);

  const doStart = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.startCampaign(campaignId);
      await loadCampaign();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doCancel = async () => {
    setBusy(true);
    try {
      await api.cancelCampaign(campaignId);
      await loadCampaign();
    } finally {
      setBusy(false);
    }
  };

  const attachAll = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.attachAllCandidates(campaignId);
      await loadCampaign();
      await loadScreenings();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const onImportFile = async (file: File) => {
    setBusy(true);
    setError(null);
    setSummary(null);
    try {
      const result = await api.importCandidatesIntoCampaign(campaignId, file);
      setSummary(result);
      await loadCampaign();
      await loadScreenings();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (!campaign) return <div className="text-slate-400">Loading…</div>;

  const s = campaign.stats;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/campaigns" className="text-sm text-slate-400 hover:text-slate-600">← All campaigns</Link>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{campaign.name}</h1>
            <p className="text-sm text-slate-500">
              {campaign.position} · {campaign.department || "—"} · {campaign.location || "—"} ·{" "}
              {campaign.experience_min}-{campaign.experience_max} yrs experience
            </p>
          </div>
          <div className="flex gap-2">
            {campaign.total_candidates === 0 && (
              <button
                onClick={attachAll}
                disabled={busy}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Add all candidates from pool
              </button>
            )}
            <label className="cursor-pointer rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Import CSV
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                disabled={busy}
                onChange={(e) => e.target.files?.[0] && onImportFile(e.target.files[0])}
              />
            </label>
            {campaign.status === "running" ? (
              <button
                onClick={doCancel}
                disabled={busy}
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
              >
                Pause Campaign
              </button>
            ) : (
              <button
                onClick={doStart}
                disabled={busy || campaign.total_candidates === 0}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
              >
                {campaign.status === "completed" ? "Re-run Remaining" : campaign.status === "paused" ? "Resume Campaign" : "Start Campaign"}
              </button>
            )}
            <a
              href={api.exportCampaignUrl(campaignId)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Export CSV
            </a>
          </div>
        </div>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
      {summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
          Imported {summary.imported}, updated {summary.updated}, skipped {summary.skipped} of {summary.total_rows} rows.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total" value={s.total} />
        <StatCard label="Shortlisted" value={s.shortlisted} accent="text-emerald-600" />
        <StatCard label="Manual Review" value={s.manual_review} accent="text-amber-600" />
        <StatCard label="Rejected" value={s.rejected} accent="text-rose-600" />
        <StatCard label="Pending" value={s.pending + s.in_progress} accent="text-slate-500" />
        <StatCard label="Failed" value={s.failed} accent="text-red-600" />
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => {
                  setActiveFilter(f.key);
                  setPage(1);
                }}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  activeFilter === f.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <input
            className="w-56 rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-slate-400"
            placeholder="Search candidate…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
              <th className="px-4 py-2">Candidate</th>
              <th className="px-4 py-2">Phone</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">AI Score</th>
              <th className="px-4 py-2">Attempts</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {screenings?.items.map((row) => (
              <tr key={row.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-medium text-slate-800">{row.candidate_name}</td>
                <td className="px-4 py-2 text-slate-500">{row.candidate_phone}</td>
                <td className="px-4 py-2">
                  <StatusBadge callStatus={row.call_status} recommendation={row.recommendation} />
                </td>
                <td className="px-4 py-2 text-slate-700">{row.ai_score ?? "—"}</td>
                <td className="px-4 py-2 text-slate-500">{row.attempt_count}</td>
                <td className="px-4 py-2 text-right">
                  <Link to={`/screenings/${row.id}`} className="text-slate-500 hover:text-slate-900">
                    View →
                  </Link>
                </td>
              </tr>
            ))}
            {screenings && screenings.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-400">
                  No candidates match this view yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {screenings && screenings.total > screenings.page_size && (
          <div className="flex items-center justify-between border-t border-slate-100 p-3 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded px-3 py-1 text-slate-600 disabled:opacity-30">
              Previous
            </button>
            <span className="text-slate-500">
              Page {screenings.page} of {Math.ceil(screenings.total / screenings.page_size)}
            </span>
            <button
              disabled={page * screenings.page_size >= screenings.total}
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
