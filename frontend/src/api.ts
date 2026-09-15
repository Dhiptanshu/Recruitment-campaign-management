const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Candidate {
  id: number;
  name: string;
  phone: string;
  email: string | null;
  current_company: string | null;
  created_at: string;
}

export interface ImportSummary {
  total_rows: number;
  imported: number;
  updated: number;
  skipped: number;
  error_count: number;
  errors: { row: number; reason: string }[];
}

export interface CampaignStats {
  total: number;
  pending: number;
  in_progress: number;
  shortlisted: number;
  manual_review: number;
  rejected: number;
  failed: number;
}

export interface Campaign {
  id: number;
  name: string;
  position: string;
  department: string | null;
  location: string | null;
  experience_min: number;
  experience_max: number;
  job_description: string | null;
  max_attempts: number;
  status: "draft" | "running" | "paused" | "completed";
  total_candidates: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  stats: CampaignStats;
}

export const MAX_EXPERIENCE_YEARS = 60;
export const MAX_RETRY_ATTEMPTS = 5;

export interface ScreeningListItem {
  id: number;
  candidate_id: number;
  candidate_name: string;
  candidate_phone: string;
  candidate_company: string | null;
  call_status: "not_contacted" | "in_progress" | "completed" | "failed";
  outcome_detail: string | null;
  recommendation: "shortlisted" | "manual_review" | "rejected" | null;
  recruiter_override: "shortlisted" | "manual_review" | "rejected" | null;
  effective_recommendation: "shortlisted" | "manual_review" | "rejected" | null;
  ai_score: number | null;
  jd_match_pct: number | null;
  attempt_count: number;
  last_attempt_at: string | null;
}

export interface InterviewSuggestion {
  suggested_within_days: number;
  reason: string;
}

export interface TranscriptTurn {
  speaker: string;
  text: string;
}

export interface ScreeningDetail {
  id: number;
  campaign_id: number;
  campaign_name: string;
  candidate: Candidate;
  call_status: string;
  outcome_detail: string | null;
  recommendation: string | null;
  ai_score: number | null;
  ai_source: "llm" | "heuristic" | null;
  summary: string | null;
  extracted_data: Record<string, any> | null;
  transcript: TranscriptTurn[] | null;
  error_message: string | null;
  call_duration_seconds: number | null;
  attempt_count: number;
  max_attempts: number;
  last_attempt_at: string | null;
  created_at: string;
  jd_match_pct: number | null;
  recruiter_note: string | null;
  recruiter_override: "shortlisted" | "manual_review" | "rejected" | null;
  effective_recommendation: "shortlisted" | "manual_review" | "rejected" | null;
  reviewed_at: string | null;
  interview_suggestion: InterviewSuggestion | null;
}

export interface LeaderboardItem {
  rank: number;
  screening_id: number;
  candidate_name: string;
  candidate_company: string | null;
  campaign_id: number;
  campaign_name: string;
  ai_score: number | null;
  jd_match_pct: number | null;
  recommendation: "shortlisted" | "manual_review" | "rejected" | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  importCandidates: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportSummary>("/api/candidates/import", { method: "POST", body: form });
  },
  listCandidates: (search: string, page: number, pageSize = 25) =>
    request<Page<Candidate>>(
      `/api/candidates?search=${encodeURIComponent(search)}&page=${page}&page_size=${pageSize}`
    ),
  candidateCount: () => request<{ total: number }>("/api/candidates/count"),

  listCampaigns: () => request<Campaign[]>("/api/campaigns"),
  getCampaign: (id: number) => request<Campaign>(`/api/campaigns/${id}`),
  createCampaign: (payload: {
    name: string;
    position: string;
    department?: string;
    location?: string;
    experience_min: number;
    experience_max: number;
    job_description?: string;
    max_attempts?: number;
  }) =>
    request<Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCampaign: (
    id: number,
    payload: Partial<{
      name: string;
      position: string;
      department: string;
      location: string;
      experience_min: number;
      experience_max: number;
      job_description: string;
      max_attempts: number;
    }>
  ) =>
    request<Campaign>(`/api/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  attachAllCandidates: (campaignId: number) =>
    request<{ added: number }>(`/api/campaigns/${campaignId}/candidates/attach_all`, { method: "POST" }),
  importCandidatesIntoCampaign: (campaignId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportSummary>(`/api/campaigns/${campaignId}/candidates/import`, {
      method: "POST",
      body: form,
    });
  },
  startCampaign: (campaignId: number) =>
    request<{ status: string }>(`/api/campaigns/${campaignId}/start`, { method: "POST" }),
  cancelCampaign: (campaignId: number) =>
    request<{ status: string }>(`/api/campaigns/${campaignId}/cancel`, { method: "POST" }),
  retryAllFailed: (campaignId: number) =>
    request<{ reset: number }>(`/api/campaigns/${campaignId}/retry_failed`, { method: "POST" }),
  listScreenings: (
    campaignId: number,
    params: { status?: string; recommendation?: string; search?: string; sort?: string; page?: number; page_size?: number }
  ) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status_filter", params.status);
    if (params.recommendation) qs.set("recommendation", params.recommendation);
    if (params.search) qs.set("search", params.search);
    if (params.sort) qs.set("sort", params.sort);
    qs.set("page", String(params.page ?? 1));
    qs.set("page_size", String(params.page_size ?? 25));
    return request<Page<ScreeningListItem>>(`/api/campaigns/${campaignId}/screenings?${qs}`);
  },
  exportCampaignUrl: (campaignId: number, format: "csv" | "xlsx" = "csv") =>
    `${BASE_URL}/api/campaigns/${campaignId}/export?format=${format}`,

  getScreening: (id: number) => request<ScreeningDetail>(`/api/screenings/${id}`),
  retryScreening: (id: number) => request<{ status: string }>(`/api/screenings/${id}/retry`, { method: "POST" }),
  submitFeedback: (
    id: number,
    payload: { note?: string; override?: "shortlisted" | "manual_review" | "rejected"; clear_override?: boolean }
  ) =>
    request<ScreeningDetail>(`/api/screenings/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getLeaderboard: (params: { campaign_id?: number; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params.campaign_id) qs.set("campaign_id", String(params.campaign_id));
    qs.set("page", String(params.page ?? 1));
    qs.set("page_size", String(params.page_size ?? 25));
    return request<Page<LeaderboardItem>>(`/api/leaderboard?${qs}`);
  },
};
