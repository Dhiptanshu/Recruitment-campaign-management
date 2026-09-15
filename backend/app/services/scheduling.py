"""Suggests how urgently a shortlisted candidate should be scheduled for
the next interview round, based on their stated notice period and score.
A heuristic, not a calendar integration -- there's no real interviewer
availability to schedule against in this prototype."""


def suggest_interview_window(extracted_data: dict | None, ai_score: int | None, effective_recommendation: str | None) -> dict | None:
    if effective_recommendation != "shortlisted":
        return None

    notice = (extracted_data or {}).get("notice_period_days")
    if notice is None:
        notice = 30

    if notice <= 15:
        days, reason = 3, f"short {notice}-day notice period"
    elif notice <= 45:
        days, reason = 7, f"{notice}-day notice period"
    elif notice <= 90:
        days, reason = 14, f"{notice}-day notice period"
    else:
        days, reason = 21, f"long {notice}-day notice period"

    if (ai_score or 0) >= 85 and days > 3:
        days = max(3, days - 2)
        reason += " -- top-scoring candidate, move quickly"

    return {"suggested_within_days": days, "reason": reason}
