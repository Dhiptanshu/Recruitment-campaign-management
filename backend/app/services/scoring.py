"""Turns raw extracted call data into a 0-100 score, a recommendation
bucket, and a short recruiter-facing summary. Pure function of
(extracted_data, campaign) so it's easy to reason about and test."""


def score_and_recommend(extracted: dict, campaign) -> tuple[int, str, str]:
    exp = extracted.get("total_experience_years") or 0
    ai_exp = extracted.get("relevant_ai_experience_years") or 0
    skills = extracted.get("skills") or {}
    comm = extracted.get("communication_quality") or 5
    conf = extracted.get("confidence_level") or 5
    depth = extracted.get("technical_depth") or 5
    current_ctc = extracted.get("current_ctc_lpa")
    expected_ctc = extracted.get("expected_ctc_lpa")

    exp_min = campaign.experience_min or 0
    exp_max = campaign.experience_max or (exp_min + 5)

    # 1. Experience fit (0-25)
    if exp_min <= exp <= exp_max:
        exp_score = 25
    else:
        distance = min(abs(exp - exp_min), abs(exp - exp_max))
        exp_score = max(0, 25 - distance * 6)

    # 2. AI/ML skill coverage (0-35)
    skill_weights = {
        "python": 8, "llms": 8, "ai_agents": 7,
        "rag_systems": 6, "fine_tuning": 3, "cloud_platforms": 3,
    }
    skill_score = sum(w for k, w in skill_weights.items() if skills.get(k))
    if ai_exp <= 0:
        skill_score = round(skill_score * 0.5)

    # 3. Recruiter-signal quality (0-30)
    signal_score = round((comm + conf + depth) / 30 * 30)

    # 4. Compensation feasibility (0-10) - penalize a very large expected jump
    comp_score = 10
    if current_ctc and expected_ctc and current_ctc > 0:
        hike = (expected_ctc - current_ctc) / current_ctc
        if hike > 1.0:
            comp_score = 2
        elif hike > 0.6:
            comp_score = 6

    score = int(max(0, min(100, exp_score + skill_score + signal_score + comp_score)))

    missing_core_skills = not (skills.get("python") and (skills.get("llms") or skills.get("ai_agents")))
    experience_far_off = exp < max(0, exp_min - 2) or exp > exp_max + 5

    if score >= 72 and not missing_core_skills and not experience_far_off:
        recommendation = "shortlisted"
    elif score < 40 or experience_far_off:
        recommendation = "rejected"
    else:
        recommendation = "manual_review"

    top_skills = [k.replace("_", " ") for k, v in skills.items() if v] or ["no specific AI/ML skills captured"]
    summary = (
        f"{exp} yrs total experience ({ai_exp} yrs relevant AI/ML). "
        f"Strong in: {', '.join(top_skills[:4])}. "
        f"Communication {comm}/10, technical depth {depth}/10. "
        f"Expected CTC {expected_ctc if expected_ctc is not None else 'n/a'} LPA "
        f"vs current {current_ctc if current_ctc is not None else 'n/a'} LPA. "
        f"AI score {score}/100 — recommended: {recommendation.replace('_', ' ')}."
    )
    return score, recommendation, summary
