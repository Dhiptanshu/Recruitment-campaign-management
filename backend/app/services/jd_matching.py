"""Matches a campaign's job-description text against the skills captured on
a call. Deterministic keyword matching (same spirit as the rest of this
prototype's "AI" -- simulated, not a real LLM call) rather than free-text
NLP, so it's fast, has no external dependency, and is easy to reason about.
"""

SKILL_KEYWORDS: dict[str, list[str]] = {
    "python": ["python"],
    "llms": ["llm", "large language model", "gpt", "openai", "chatgpt", "generative ai", "genai"],
    "ai_agents": ["agent", "agentic", "autonomous agent"],
    "rag_systems": ["rag", "retrieval augmented", "retrieval-augmented", "vector database", "vector db", "embeddings"],
    "fine_tuning": ["fine-tun", "finetun", "fine tun", "lora", "peft"],
    "cloud_platforms": ["aws", "azure", "gcp", "google cloud", "cloud platform", "cloud infrastructure"],
}


def match_job_description(
    job_description: str | None, skills: dict | None
) -> tuple[int | None, list[str], list[str]]:
    """Returns (match_pct, matched_skill_keys, missing_skill_keys).

    match_pct is None when the JD has no text or mentions none of the
    recognized skill keywords -- distinct from a real 0% (candidate matches
    none of the requirements the JD actually names).
    """
    if not job_description or not job_description.strip():
        return None, [], []

    text = job_description.lower()
    skills = skills or {}

    jd_requires = [key for key, terms in SKILL_KEYWORDS.items() if any(term in text for term in terms)]
    if not jd_requires:
        return None, [], []

    matched = [k for k in jd_requires if skills.get(k)]
    missing = [k for k in jd_requires if not skills.get(k)]
    pct = round(len(matched) / len(jd_requires) * 100)
    return pct, matched, missing
