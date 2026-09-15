import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Campaign } from "../api";
import { ProgressBar } from "../components/ProgressBar";

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const navigate = useNavigate();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    position: "",
    department: "",
    location: "",
    experience_min: 0,
    experience_max: 8,
    job_description: "",
  });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.listCampaigns().then(setCampaigns);
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.name || !form.position) {
      setError("Campaign name and position are required");
      return;
    }
    if (form.experience_min > form.experience_max) {
      setError("Minimum experience cannot exceed maximum");
      return;
    }
    setCreating(true);
    try {
      const campaign = await api.createCampaign(form);
      navigate(`/campaigns/${campaign.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Campaigns</h1>
          <p className="mt-1 text-sm text-slate-500">Create and track AI screening campaigns.</p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          {showForm ? "Cancel" : "+ New Campaign"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="text-xs font-medium text-slate-500">Campaign Name *</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              placeholder="AI Engineer Hiring – Screening Round"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Position *</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              placeholder="AI Engineer"
              value={form.position}
              onChange={(e) => setForm({ ...form, position: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Department</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              placeholder="Engineering"
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Location</label>
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              placeholder="Ahmedabad / Remote"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-medium text-slate-500">Min Experience (yrs)</label>
              <input
                type="number"
                min={0}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
                value={form.experience_min}
                onChange={(e) => setForm({ ...form, experience_min: Number(e.target.value) })}
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-slate-500">Max Experience (yrs)</label>
              <input
                type="number"
                min={0}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
                value={form.experience_max}
                onChange={(e) => setForm({ ...form, experience_max: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs font-medium text-slate-500">Job Description (optional)</label>
            <textarea
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              rows={3}
              value={form.job_description}
              onChange={(e) => setForm({ ...form, job_description: e.target.value })}
            />
          </div>
          {error && <div className="sm:col-span-2 text-sm text-rose-600">{error}</div>}
          <div className="sm:col-span-2">
            <button
              disabled={creating}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create Campaign"}
            </button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {campaigns?.map((c) => (
          <Link
            key={c.id}
            to={`/campaigns/${c.id}`}
            className="block rounded-xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-slate-900">{c.name}</div>
                <div className="text-sm text-slate-500">
                  {c.position} · {c.location || "—"} · {c.experience_min}-{c.experience_max} yrs
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  c.status === "running"
                    ? "bg-sky-100 text-sky-700"
                    : c.status === "completed"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {c.status}
              </span>
            </div>
            <div className="mt-4">
              <ProgressBar
                segments={[
                  { value: c.stats.shortlisted, color: "bg-emerald-500", label: "Shortlisted" },
                  { value: c.stats.manual_review, color: "bg-amber-400", label: "Manual Review" },
                  { value: c.stats.rejected, color: "bg-rose-400", label: "Rejected" },
                  { value: c.stats.pending + c.stats.in_progress, color: "bg-slate-300", label: "Pending" },
                  { value: c.stats.failed, color: "bg-red-500", label: "Failed" },
                ]}
              />
            </div>
            <div className="mt-3 text-sm text-slate-500">{c.stats.total} candidates total</div>
          </Link>
        ))}
        {campaigns && campaigns.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-400">
            No campaigns yet. Create one to get started.
          </div>
        )}
      </div>
    </div>
  );
}
