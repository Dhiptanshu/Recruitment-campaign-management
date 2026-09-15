import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { ScreeningDetail } from "../api";
import { StatusBadge } from "../components/Badge";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-0.5 text-sm text-slate-800">{value ?? "—"}</div>
    </div>
  );
}

function boolLabel(v: any) {
  if (v === true) return "Yes";
  if (v === false) return "No";
  return "—";
}

const OVERRIDE_OPTIONS: { value: "shortlisted" | "manual_review" | "rejected"; label: string }[] = [
  { value: "shortlisted", label: "Shortlist" },
  { value: "manual_review", label: "Manual Review" },
  { value: "rejected", label: "Reject" },
];

export function ScreeningDetailPage() {
  const { id } = useParams();
  const screeningId = Number(id);
  const [s, setS] = useState<ScreeningDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [noteDraft, setNoteDraft] = useState("");
  const [overrideDraft, setOverrideDraft] = useState<"shortlisted" | "manual_review" | "rejected" | null>(null);
  const [savingFeedback, setSavingFeedback] = useState(false);

  const load = () => api.getScreening(screeningId).then((data) => {
    setS(data);
    setNoteDraft(data.recruiter_note ?? "");
    setOverrideDraft(data.recruiter_override);
  }).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, [screeningId]);

  useEffect(() => {
    if (s?.call_status !== "in_progress") return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [s?.call_status]);

  const retry = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.retryScreening(screeningId);
      setTimeout(load, 800);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveFeedback = async () => {
    setSavingFeedback(true);
    setError(null);
    try {
      const updated = await api.submitFeedback(screeningId, {
        note: noteDraft,
        ...(overrideDraft ? { override: overrideDraft } : { clear_override: true }),
      });
      setS(updated);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSavingFeedback(false);
    }
  };

  if (!s) return <div className="text-slate-400">Loading…</div>;
  const d = s.extracted_data || {};
  const skills = d.skills || {};
  const jdMatch = d.jd_match as { pct: number; matched: string[]; missing: string[] } | undefined;
  const feedbackDirty = noteDraft !== (s.recruiter_note ?? "") || overrideDraft !== s.recruiter_override;

  return (
    <div className="space-y-6">
      <Link to={`/campaigns/${s.campaign_id}`} className="text-sm text-slate-400 hover:text-slate-600">
        ← {s.campaign_name}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">{s.candidate.name}</h1>
          <p className="text-sm text-slate-500">{s.candidate.phone} · {s.candidate.email || "no email"} · {s.candidate.current_company || "—"}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge callStatus={s.call_status} recommendation={s.effective_recommendation} />
          {s.ai_score !== null && (
            <span className="rounded-full bg-slate-900 px-3 py-1 text-sm font-semibold text-white">{s.ai_score}/100</span>
          )}
        </div>
      </div>

      {error && <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Call Status" value={s.call_status === "in_progress" ? "Calling…" : s.call_status.replace("_", " ")} />
        <Field label="Outcome" value={s.outcome_detail?.replace("_", " ")} />
        <Field label="Attempts" value={`${s.attempt_count} / ${s.max_attempts}`} />
        <Field label="Call Duration" value={s.call_duration_seconds != null ? `${s.call_duration_seconds}s` : "—"} />
        <Field label="Last Attempt" value={s.last_attempt_at ? new Date(s.last_attempt_at).toLocaleString() : "—"} />
        <Field
          label="Recommendation"
          value={
            s.recruiter_override
              ? `${s.recruiter_override.replace("_", " ")} (recruiter override, AI said ${s.recommendation?.replace("_", " ")})`
              : s.recommendation?.replace("_", " ")
          }
        />
      </div>

      {s.interview_suggestion && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <span className="font-semibold">Suggested next step:</span> schedule the interview within{" "}
          {s.interview_suggestion.suggested_within_days} day{s.interview_suggestion.suggested_within_days === 1 ? "" : "s"} —{" "}
          {s.interview_suggestion.reason}.
        </div>
      )}

      {(s.call_status === "failed" || s.call_status === "not_contacted") && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          {s.error_message && <p className="text-sm text-amber-800">Last error: {s.error_message}</p>}
          <button
            onClick={retry}
            disabled={busy}
            className="mt-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {busy ? "Retrying…" : "Retry Call"}
          </button>
        </div>
      )}

      {s.summary && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">AI Summary</h2>
          <p className="mt-2 text-sm text-slate-600">{s.summary}</p>
        </div>
      )}

      {s.call_status === "completed" && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Candidate Details & Compensation</h2>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Field label="Designation" value={d.current_designation} />
              <Field label="Location" value={d.current_location} />
              <Field label="Total Experience" value={d.total_experience_years != null ? `${d.total_experience_years} yrs` : null} />
              <Field label="Relevant AI Experience" value={d.relevant_ai_experience_years != null ? `${d.relevant_ai_experience_years} yrs` : null} />
              <Field label="Current CTC" value={d.current_ctc_lpa != null ? `₹${d.current_ctc_lpa} LPA` : null} />
              <Field label="Expected CTC" value={d.expected_ctc_lpa != null ? `₹${d.expected_ctc_lpa} LPA` : null} />
              <Field label="Salary Negotiable" value={boolLabel(d.salary_negotiable)} />
              <Field label="Notice Period" value={d.notice_period_days != null ? `${d.notice_period_days} days` : null} />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Technical Screening</h2>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Field label="Primary Language" value={d.primary_language} />
              <Field label="Python" value={boolLabel(skills.python)} />
              <Field label="LLMs" value={boolLabel(skills.llms)} />
              <Field label="AI Agents" value={boolLabel(skills.ai_agents)} />
              <Field label="RAG Systems" value={boolLabel(skills.rag_systems)} />
              <Field label="Fine-Tuning" value={boolLabel(skills.fine_tuning)} />
              <Field label="Cloud Platforms" value={boolLabel(skills.cloud_platforms)} />
            </div>
          </div>

          {jdMatch && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">Job Description Match</h2>
                <span className="rounded-full bg-slate-900 px-2.5 py-0.5 text-xs font-semibold text-white">{jdMatch.pct}%</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {jdMatch.matched.map((k) => (
                  <span key={k} className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                    {k.replace("_", " ")}
                  </span>
                ))}
                {jdMatch.missing.map((k) => (
                  <span key={k} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500 line-through">
                    {k.replace("_", " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Project Experience</h2>
            <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Field label="Team Size" value={d.team_size} />
              <Field label="Role" value={d.role_in_project} />
            </div>
            {d.projects && d.projects.length > 0 ? (
              <ul className="mt-3 list-inside list-disc text-sm text-slate-700">
                {d.projects.map((p: string, i: number) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-slate-400">No projects captured.</p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Recruiter Signals</h2>
            <div className="mt-3 grid grid-cols-3 gap-4">
              <Field label="Communication" value={d.communication_quality != null ? `${d.communication_quality}/10` : null} />
              <Field label="Confidence" value={d.confidence_level != null ? `${d.confidence_level}/10` : null} />
              <Field label="Technical Depth" value={d.technical_depth != null ? `${d.technical_depth}/10` : null} />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Recruiter Review</h2>
            <p className="mt-1 text-xs text-slate-400">
              Override the AI's call, or leave it as-is and just add a note. The override always wins over the AI recommendation.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => setOverrideDraft(null)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  overrideDraft === null ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                Keep AI ({s.recommendation?.replace("_", " ")})
              </button>
              {OVERRIDE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setOverrideDraft(opt.value)}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    overrideDraft === opt.value ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <textarea
              className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
              rows={3}
              placeholder="Add a note for the team (optional)…"
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
            />
            <div className="mt-2 flex items-center gap-3">
              <button
                onClick={saveFeedback}
                disabled={savingFeedback || !feedbackDirty}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
              >
                {savingFeedback ? "Saving…" : "Save Review"}
              </button>
              {s.reviewed_at && !feedbackDirty && (
                <span className="text-xs text-slate-400">Last reviewed {new Date(s.reviewed_at).toLocaleString()}</span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
