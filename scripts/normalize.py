"""
normalize.py
Small helper functions that clean up the messy fields we found in the
3 source CSVs. Each function fixes ONE specific problem — keeping them
separate makes it easy to explain (and defend) each decision on its own.
"""

import re


def normalize_phone(raw: str) -> str | None:
    """
    Phones show up as:
      9000000268 | +919000000254 | 919000000231 | 09000000287 | +91-9000000131
    We reduce all of these to just the last 10 digits, which is the
    actual Indian mobile number without country code or leading zero.
    """
    if not raw or not str(raw).strip():
        return None
    digits = re.sub(r"\D", "", str(raw))  # strip +, -, spaces etc.
    if len(digits) < 10:
        return None
    return digits[-10:]  # keep last 10 digits regardless of prefix


def normalize_email(raw: str) -> str | None:
    """Emails differ only in case (ISHA.CHOPRA95@... vs isha.chopra95@...)."""
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().lower()


def normalize_city(raw: str) -> str | None:
    """
    Cities have trailing spaces, mixed case, and Gurgaon/Gurugram used
    interchangeably (same city, renamed a few years ago -> we treat them
    as the same place). We do NOT merge 'Delhi' and 'New Delhi' /
    'Delhi NCR' automatically -> that's a judgement call, flagged as-is
    in the data issues report rather than silently guessed at.
    """
    if not raw or not str(raw).strip():
        return None
    city = str(raw).strip().lower()
    if city in ("gurugram", "gurgaon"):
        city = "gurgaon"
    return city.title()


def normalize_name(raw: str) -> str | None:
    """Trim whitespace and title-case, purely for fuzzy-matching fallback."""
    if not raw or not str(raw).strip():
        return None
    return " ".join(str(raw).strip().split()).title()


def normalize_status(raw: str) -> str | None:
    """
    Source 2 'status' column has Active/active/ACTIVE/Inactive/paused.
    'paused' is a genuinely different state, not just a casing issue of
    Active — we keep it as its own value rather than collapsing it in.
    """
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().lower()


def normalize_verified(raw: str) -> bool | None:
    """Source 3 'Verified' column: Y/N/yes/No/Yes -> normalize to True/False."""
    if raw is None or not str(raw).strip():
        return None
    val = str(raw).strip().lower()
    return val in ("y", "yes", "true", "1")


def parse_ctc(raw) -> float | None:
    """
    Source 1 'Current CTC' mixes two units in the SAME column:
      417964      -> looks like an annual rupee salary
      4.2, 8.3    -> looks like the same thing expressed in LAKHS (4.2 lakh = 420000)
    Rule: if the value is small (< 1000) we assume it's in lakhs and
    multiply by 100000 to get a consistent annual-rupee figure.
    This assumption is explicitly called out in the data issues report --
    it's a judgement call, not a certainty.
    """
    if raw is None or str(raw).strip() == "":
        return None
    val = float(raw)
    if val < 1000:
        return round(val * 100000, 2)
    return val


def parse_rate(raw: str):
    """
    Source 2 'rate' mixes '1415/hr' and '15k/month' style strings.
    We convert everything to an estimated monthly rupee rate so gig
    workers can be compared on one number:
      /hr    -> assume ~160 working hours/month
      k/month -> multiply by 1000
    """
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip().lower()
    if "/hr" in raw:
        hourly = float(raw.replace("/hr", "").strip())
        return round(hourly * 160, 2)
    if "k/month" in raw:
        monthly_k = float(raw.replace("k/month", "").strip())
        return round(monthly_k * 1000, 2)
    return None


def normalize_skills(raw: str) -> list[str]:
    """Lowercase + trim each skill so 'REST APIs' == 'rest apis'."""
    if not raw or not str(raw).strip():
        return []
    return [s.strip().lower() for s in str(raw).split(",") if s.strip()]
