const RECOMMENDATION_STYLES: Record<string, string> = {
  shortlisted: "bg-emerald-100 text-emerald-700 ring-emerald-600/20",
  manual_review: "bg-amber-100 text-amber-700 ring-amber-600/20",
  rejected: "bg-rose-100 text-rose-700 ring-rose-600/20",
};

const BUCKET_LABEL: Record<string, string> = {
  shortlisted: "Shortlisted",
  manual_review: "Manual Review",
  rejected: "Rejected",
};

export function bucketFor(callStatus: string, recommendation: string | null): string {
  if (callStatus === "failed") return "failed";
  if (callStatus === "completed" && recommendation) return recommendation;
  return "pending";
}

const BUCKET_STYLES: Record<string, string> = {
  ...RECOMMENDATION_STYLES,
  pending: "bg-slate-100 text-slate-600 ring-slate-500/20",
  failed: "bg-red-100 text-red-700 ring-red-600/20",
};

const BUCKET_LABELS: Record<string, string> = {
  ...BUCKET_LABEL,
  pending: "Pending",
  failed: "Failed",
};

export function StatusBadge({ callStatus, recommendation }: { callStatus: string; recommendation: string | null }) {
  const bucket = bucketFor(callStatus, recommendation);
  const label = callStatus === "in_progress" ? "Calling…" : BUCKET_LABELS[bucket] ?? bucket;
  const style = callStatus === "in_progress" ? "bg-sky-100 text-sky-700 ring-sky-600/20" : BUCKET_STYLES[bucket];
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}>
      {label}
    </span>
  );
}
