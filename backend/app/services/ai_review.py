"""Single entry point the campaign runner calls to turn one call's extracted
data into a score/recommendation/summary. Tries the real LLM first (if
configured); on any failure, transparently falls back to the deterministic
heuristic scorer so a campaign never stalls because of an upstream LLM
outage. `source` tells the caller (and eventually the recruiter, via the
candidate page) which path actually produced the result."""
import logging

from . import llm_client
from .scoring import score_and_recommend

logger = logging.getLogger("globalvox.ai_review")


def generate_ai_review(extracted_data: dict, campaign) -> tuple[int, str, str, str]:
    if llm_client.is_configured():
        try:
            result = llm_client.generate_review(extracted_data, campaign)
            return result["score"], result["recommendation"], result["summary"], "llm"
        except llm_client.LLMUnavailable as exc:
            logger.warning("LLM review unavailable, falling back to heuristic scorer: %s", exc)

    score, recommendation, summary = score_and_recommend(extracted_data, campaign)
    return score, recommendation, summary, "heuristic"
