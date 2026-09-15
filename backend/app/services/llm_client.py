"""Thin client for an OpenAI-compatible chat-completions endpoint (aicredits.in
by default). Used to generate the candidate's AI score/recommendation/summary
for real, instead of the deterministic fallback in scoring.py.

Fully optional: with no LLM_API_KEY set, is_configured() is False and callers
are expected to skip straight to the heuristic scorer. Every failure mode
(network error, timeout, bad status, malformed/invalid JSON) is normalized
into LLMUnavailable so callers have exactly one exception to catch.
"""
import json
import logging
import os

import httpx

logger = logging.getLogger("globalvox.llm_client")

LLM_API_BASE_URL = os.environ.get("LLM_API_BASE_URL", "https://aicredits.in/v1").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "15"))

VALID_RECOMMENDATIONS = {"shortlisted", "manual_review", "rejected"}

SYSTEM_PROMPT = (
    "You are an AI recruiting assistant scoring a candidate screening call for an AI Engineer "
    "hiring campaign. You will be given the campaign's requirements and the structured data "
    "extracted from the call. Respond with ONLY a JSON object with exactly these keys: "
    '"score" (integer 0-100, how well this candidate fits the role), '
    '"recommendation" (one of "shortlisted", "manual_review", "rejected"), and '
    '"summary" (a concise 2-4 sentence recruiter-facing summary of the candidate). '
    "No prose outside the JSON object."
)


class LLMUnavailable(Exception):
    """Raised for any failure mode -- missing key, network error, timeout,
    bad HTTP status, or a response that doesn't parse into the expected
    shape. Callers should catch this and fall back to the heuristic scorer."""


def is_configured() -> bool:
    return bool(LLM_API_KEY)


def generate_review(extracted_data: dict, campaign) -> dict:
    if not LLM_API_KEY:
        raise LLMUnavailable("LLM_API_KEY is not configured")

    user_prompt = json.dumps({
        "campaign": {
            "position": campaign.position,
            "experience_min_years": campaign.experience_min,
            "experience_max_years": campaign.experience_max,
            "job_description": campaign.job_description,
        },
        "candidate_call_data": extracted_data,
    })

    try:
        resp = httpx.post(
            f"{LLM_API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise LLMUnavailable(f"LLM request timed out: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise LLMUnavailable(f"LLM returned HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"LLM request failed: {exc}") from exc

    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise LLMUnavailable(f"LLM response could not be parsed: {exc}") from exc

    score = parsed.get("score")
    recommendation = parsed.get("recommendation")
    summary = parsed.get("summary")

    if not isinstance(score, (int, float)) or isinstance(score, bool) or not (0 <= score <= 100):
        raise LLMUnavailable(f"LLM returned an invalid score: {score!r}")
    if recommendation not in VALID_RECOMMENDATIONS:
        raise LLMUnavailable(f"LLM returned an invalid recommendation: {recommendation!r}")
    if not isinstance(summary, str) or not summary.strip():
        raise LLMUnavailable("LLM returned an empty summary")

    return {"score": int(round(score)), "recommendation": recommendation, "summary": summary.strip()}
