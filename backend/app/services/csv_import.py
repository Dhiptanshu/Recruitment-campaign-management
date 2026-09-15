import csv
import io
import re

from sqlalchemy.orm import Session

from ..models import Candidate

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = {"name", "phone"}
BATCH_SIZE = 500


class ImportSummary:
    def __init__(self):
        self.total_rows = 0
        self.imported = 0
        self.updated = 0
        self.skipped = 0
        self.errors: list[dict] = []  # {row, reason}
        self.touched_candidate_ids: list[int] = []

    def to_dict(self):
        return {
            "total_rows": self.total_rows,
            "imported": self.imported,
            "updated": self.updated,
            "skipped": self.skipped,
            "error_count": len(self.errors),
            "errors": self.errors[:50],
        }


def _clean(value):
    if value is None:
        return None
    v = value.strip()
    return v if v else None


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^0-9+]", "", phone)


def validate_row(row: dict) -> tuple[dict | None, str | None]:
    name = _clean(row.get("name"))
    phone_raw = _clean(row.get("phone"))
    email = _clean(row.get("email"))
    company = _clean(row.get("current_company"))

    if not name:
        return None, "missing name"
    if not phone_raw:
        return None, "missing phone"
    phone = _normalize_phone(phone_raw)
    if not PHONE_RE.match(phone):
        return None, f"invalid phone '{phone_raw}'"
    if email and not EMAIL_RE.match(email):
        return None, f"invalid email '{email}'"

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "current_company": company,
        "external_ref": _clean(row.get("id")),
    }, None


def import_candidates_csv(db: Session, file_bytes: bytes) -> ImportSummary:
    summary = ImportSummary()

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        summary.errors.append({"row": 0, "reason": "empty file"})
        return summary

    header = {h.strip().lower() for h in reader.fieldnames if h}
    missing_cols = REQUIRED_COLUMNS - header
    if missing_cols:
        summary.errors.append({
            "row": 0,
            "reason": f"missing required column(s): {', '.join(sorted(missing_cols))}",
        })
        return summary

    # normalize keys to lowercase for lookups regardless of CSV header casing.
    # keyed by phone so duplicate phones within one flush cycle collapse to
    # the last occurrence instead of violating the unique constraint.
    batch: dict[str, dict] = {}

    def flush():
        nonlocal batch
        if not batch:
            return
        existing = {
            c.phone: c for c in db.query(Candidate).filter(Candidate.phone.in_(batch.keys())).all()
        }
        new_candidates = []
        for phone, rec in batch.items():
            existing_candidate = existing.get(phone)
            if existing_candidate:
                existing_candidate.name = rec["name"]
                existing_candidate.email = rec["email"] or existing_candidate.email
                existing_candidate.current_company = rec["current_company"] or existing_candidate.current_company
                summary.updated += 1
                summary.touched_candidate_ids.append(existing_candidate.id)
            else:
                candidate = Candidate(**rec)
                db.add(candidate)
                new_candidates.append(candidate)
                summary.imported += 1
        db.flush()
        summary.touched_candidate_ids.extend(c.id for c in new_candidates)
        db.commit()
        batch = {}

    for i, raw_row in enumerate(reader, start=2):  # header is row 1
        summary.total_rows += 1
        normalized_row = {(k or "").strip().lower(): v for k, v in raw_row.items()}
        record, error = validate_row(normalized_row)
        if error:
            summary.skipped += 1
            if len(summary.errors) < 200:
                summary.errors.append({"row": i, "reason": error})
            continue
        batch[record["phone"]] = record
        if len(batch) >= BATCH_SIZE:
            flush()

    flush()
    return summary
