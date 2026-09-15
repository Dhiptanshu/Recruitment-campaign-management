import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Campaign, LeaderboardItem, Page } from "../api";
import { StatusBadge } from "../components/Badge";

export function LeaderboardPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState<number | "">("");
  const [data, setData] = useState<Page<LeaderboardItem> | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listCampaigns().then(setCampaigns).catch(() => {});
  }, []);

  useEffect(() => {
    api
      .getLeaderboard({ campaign_id: campaignId ? Number(campaignId) : undefined, page })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [campaignId, page]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Leaderboard</h1>
          <p className="mt-1 text-sm text-slate-500">Top-scoring candidates, ranked across all campaigns.</p>
        </div>
        <select
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
          value={campaignId}
          onChange={(e) => {
            setCampaignId(e.target.value ? Number(e.target.value) : "");
            setPage(1);
          }}
        >
          <option value="">All campaigns</option>
          {campaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      <div className="rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
              <th className="px-4 py-2">Rank</th>
              <th className="px-4 py-2">Candidate</th>
              <th className="px-4 py-2">Campaign</th>
              <th className="px-4 py-2">Company</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">AI Score</th>
              <th className="px-4 py-2">JD Match</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {data?.items.map((row) => (
              <tr key={row.screening_id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2 font-semibold text-slate-400">#{row.rank}</td>
                <td className="px-4 py-2 font-medium text-slate-800">{row.candidate_name}</td>
                <td className="px-4 py-2 text-slate-500">{row.campaign_name}</td>
                <td className="px-4 py-2 text-slate-500">{row.candidate_company ?? "—"}</td>
                <td className="px-4 py-2">
                  <StatusBadge callStatus="completed" recommendation={row.recommendation} />
                </td>
                <td className="px-4 py-2 font-semibold text-slate-800">{row.ai_score ?? "—"}</td>
                <td className="px-4 py-2 text-slate-700">{row.jd_match_pct != null ? `${row.jd_match_pct}%` : "—"}</td>
                <td className="px-4 py-2 text-right">
                  <Link to={`/screenings/${row.screening_id}`} className="text-slate-500 hover:text-slate-900">
                    View →
                  </Link>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                  No completed screenings yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-slate-100 p-3 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded px-3 py-1 text-slate-600 disabled:opacity-30">
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
