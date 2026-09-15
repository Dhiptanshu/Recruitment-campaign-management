"""
Simulated external AI voice-calling provider.

Stands in for the "external service that represents the AI recruitment
calling system" described in the assessment brief. It is intentionally
imperfect (raises transient errors, times out, returns partial data) so the
rest of the application has to handle a flaky third-party dependency the
way it would in production. Nothing here makes a real phone call.
"""
import random
import time
from dataclasses import dataclass, field
from typing import Optional


class CallingServiceError(Exception):
    """Raised for transient provider-side failures (retryable)."""


PRIMARY_LANGUAGES = ["Python", "Java", "JavaScript/TypeScript", "Go", "C++"]
CLOUD_PLATFORMS = ["AWS", "GCP", "Azure", "AWS + GCP", "None"]
PROJECT_POOL = [
    "RAG-based customer support assistant",
    "LLM-powered document summarizer",
    "Fine-tuned classification model for support tickets",
    "AI agent for internal workflow automation",
    "GPT-powered knowledge search platform",
    "Voice-based conversational assistant",
    "Recommendation engine using embeddings",
    "Computer vision defect-detection pipeline",
]

# Outcome weights per call attempt.
OUTCOME_WEIGHTS = [
    ("success", 0.68),
    ("no_answer", 0.12),
    ("voicemail", 0.08),
    ("technical_error", 0.12),
]


@dataclass
class CallResult:
    outcome: str  # success | no_answer | voicemail
    duration_seconds: int
    data: dict = field(default_factory=dict)


def _weighted_choice(weights):
    r = random.random()
    upto = 0.0
    for label, w in weights:
        upto += w
        if r <= upto:
            return label
    return weights[-1][0]


def _simulate_extracted_data(campaign: dict) -> dict:
    exp_min = campaign.get("experience_min") or 0
    exp_max = campaign.get("experience_max") or (exp_min + 5)
    # bias experience around the campaign's target range, with some outliers
    total_experience = round(random.uniform(max(0, exp_min - 3), exp_max + 4), 1)
    relevant_ai_experience = round(min(total_experience, random.uniform(0, total_experience)), 1)

    current_ctc = round(random.uniform(6, 45), 1)
    bump = random.uniform(1.15, 1.6)
    expected_ctc = round(current_ctc * bump, 1)

    skills = {
        "python": random.random() < 0.85,
        "llms": random.random() < 0.7,
        "ai_agents": random.random() < 0.5,
        "rag_systems": random.random() < 0.55,
        "fine_tuning": random.random() < 0.35,
        "cloud_platforms": random.random() < 0.75,
    }

    num_projects = random.randint(0, 4)
    projects = random.sample(PROJECT_POOL, k=min(num_projects, len(PROJECT_POOL)))

    return {
        "current_designation": random.choice([
            "Software Engineer", "Senior Software Engineer", "ML Engineer",
            "AI Engineer", "Data Scientist", "Backend Engineer", "Applied Scientist",
        ]),
        "total_experience_years": total_experience,
        "relevant_ai_experience_years": relevant_ai_experience,
        "current_location": random.choice([
            "Ahmedabad", "Bengaluru", "Pune", "Hyderabad", "Mumbai", "Remote", "Delhi NCR",
        ]),
        "current_ctc_lpa": current_ctc,
        "expected_ctc_lpa": expected_ctc,
        "salary_negotiable": random.random() < 0.6,
        "notice_period_days": random.choice([0, 15, 30, 45, 60, 90]),
        "primary_language": random.choice(PRIMARY_LANGUAGES),
        "skills": skills,
        "projects": projects,
        "team_size": random.choice([None, 1, 2, 3, 5, 8, 12]),
        "role_in_project": random.choice([
            "Individual contributor", "Tech lead", "Contributor in a larger team", "Solo builder",
        ]) if projects else None,
        "communication_quality": random.randint(4, 10),
        "confidence_level": random.randint(4, 10),
        "technical_depth": random.randint(3, 10),
    }


def place_call(candidate: dict, campaign: dict) -> CallResult:
    """
    Simulate one outbound AI screening call.

    Raises CallingServiceError for transient provider failures (network
    blip, upstream timeout) that a caller should retry. Otherwise returns a
    CallResult describing what "happened" on the call.
    """
    # simulated network/processing latency (kept short so the demo is fast;
    # duration_seconds below is the *simulated* call length shown to users)
    time.sleep(random.uniform(0.05, 0.25))

    outcome = _weighted_choice(OUTCOME_WEIGHTS)

    if outcome == "technical_error":
        raise CallingServiceError(random.choice([
            "Upstream telephony provider timed out",
            "No available call lines, provider at capacity",
            "Malformed response from voice provider",
        ]))

    if outcome == "no_answer":
        return CallResult(outcome="no_answer", duration_seconds=0)

    if outcome == "voicemail":
        return CallResult(outcome="voicemail", duration_seconds=random.randint(8, 25))

    data = _simulate_extracted_data(campaign)
    # occasionally the provider returns a partial extraction (imperfect
    # speech-to-data pipeline) - the caller must tolerate missing fields
    if random.random() < 0.06:
        for key in random.sample(list(data.keys()), k=min(3, len(data))):
            data[key] = None

    duration = random.randint(90, 480)
    return CallResult(outcome="success", duration_seconds=duration, data=data)
