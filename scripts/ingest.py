"""
ingest.py
Task 1 — merges data/source1_naukri_applicants.csv, source2_gig_workers.csv,
and source3_cbnexus_contacts.csv into one SQLite database (db/consultbae.db).

Run with:  python scripts/ingest.py
"""

import csv
import json
import sqlite3
from pathlib import Path

from normalize import (
    normalize_phone, normalize_email, normalize_city, normalize_name,
    normalize_status, normalize_verified, parse_ctc, parse_rate,
    normalize_skills,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "db" / "consultbae.db"


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if any(v.strip() for v in row.values())]
        # the "any(v.strip() ...)" filters out the fully-blank row we found in source2


def load_source1():
    """Naukri applicants: has BOTH email and phone -> our anchor source."""
    rows = load_csv(DATA_DIR / "source1_naukri_applicants.csv")
    cleaned = []
    for r in rows:
        cleaned.append({
            "source": "naukri",
            "name": normalize_name(r["Full Name"]),
            "email": normalize_email(r["Email"]),
            "phone": normalize_phone(r["Phone"]),
            "city": normalize_city(r["City"]),
            "experience_years": float(r["Experience (Years)"]) if r["Experience (Years)"] else None,
            "ctc_annual": parse_ctc(r["Current CTC"]),
            "applied_date_raw": r["Applied Date"],  # dates are also inconsistent formats -
            # left raw here; see data issues report re: 4+ date formats found
            "skills": normalize_skills(r["Skills"]),
            "raw": r,
        })
    return cleaned


def load_source2():
    """Gig workers: has email but NOT phone."""
    rows = load_csv(DATA_DIR / "source2_gig_workers.csv")
    cleaned = []
    for r in rows:
        # guard against the shifted/malformed row we found
        # (skill_tags value landed in the email_id column)
        if "@" not in (r.get("email_id") or ""):
            continue
        cleaned.append({
            "source": "gig_worker",
            "name": normalize_name(r["worker_name"]),
            "email": normalize_email(r["email_id"]),
            "phone": None,
            "city": normalize_city(r["location"]),
            "rate_monthly_est": parse_rate(r["rate"]),
            "status": normalize_status(r["status"]),
            "skills": normalize_skills(r["skill_tags"]),
            "raw": r,
        })
    return cleaned


def load_source3():
    """CBNexus contacts: has phone but NOT email."""
    rows = load_csv(DATA_DIR / "source3_cbnexus_contacts.csv")
    cleaned = []
    for r in rows:
        if r["Name"] == "Name":
            continue  # header row got repeated mid-file in source3 - skip duplicates
        cleaned.append({
            "source": "cbnexus",
            "name": normalize_name(r["Name"]),
            "email": None,
            "phone": normalize_phone(r["Phone Number"]),
            "city": normalize_city(r["City"]),
            "verified": normalize_verified(r["Verified"]),
            "projects_completed": int(r["Projects Completed"]) if r["Projects Completed"] else None,
            "raw": r,
        })
    return cleaned


def match_people(s1, s2, s3):
    """
    Matching strategy (in order of confidence):
      1. exact email match  (links source1 <-> source2)
      2. exact phone match  (links source1 <-> source3)
      3. fuzzy name+city match for anything left unmatched (low confidence)

    Returns a list of "clusters" - each cluster is a dict of
    {source_name: [row, row...]} representing ONE real person.
    """
    clusters = []

    def find_cluster(email=None, phone=None, name=None, city=None):
        for c in clusters:
            for rows in c.values():
                for r in rows:
                    if email and r.get("email") and r["email"] == email:
                        return c
                    if phone and r.get("phone") and r["phone"] == phone:
                        return c
                    if name and city and r.get("name") == name and r.get("city") == city:
                        return c
        return None

    for row in s1 + s2 + s3:
        c = find_cluster(email=row.get("email"), phone=row.get("phone"))
        if c is None:
            c = find_cluster(name=row.get("name"), city=row.get("city"))
            if c is not None:
                row["_match_confidence"] = "fuzzy"
        else:
            row["_match_confidence"] = "exact"

        if c is None:
            c = {}
            clusters.append(c)
        c.setdefault(row["source"], []).append(row)

    return clusters


def build_database(clusters):
    DB_PATH.parent.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # rebuild fresh each run so the script is repeatable

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE people (
            person_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT,
            canonical_email TEXT,
            canonical_phone TEXT,
            canonical_city TEXT,
            match_confidence TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE source_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER REFERENCES people(person_id),
            source_name TEXT,
            raw_json TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE audio_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER REFERENCES people(person_id),
            name TEXT,
            phone TEXT,
            file_path TEXT,
            duration_sec REAL,
            sample_rate_hz INTEGER,
            bitrate_kbps REAL,
            loudness_db REAL,
            submitted_at TEXT
        )
    """)

    for cluster in clusters:
        all_rows = [r for rows in cluster.values() for r in rows]
        name = next((r["name"] for r in all_rows if r.get("name")), None)
        email = next((r["email"] for r in all_rows if r.get("email")), None)
        phone = next((r["phone"] for r in all_rows if r.get("phone")), None)
        city = next((r["city"] for r in all_rows if r.get("city")), None)
        confidence = "fuzzy" if any(r.get("_match_confidence") == "fuzzy" for r in all_rows) else "exact"

        cur.execute(
            "INSERT INTO people (canonical_name, canonical_email, canonical_phone, canonical_city, match_confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, city, confidence),
        )
        person_id = cur.lastrowid

        for r in all_rows:
            cur.execute(
                "INSERT INTO source_records (person_id, source_name, raw_json) VALUES (?, ?, ?)",
                (person_id, r["source"], json.dumps(r["raw"])),
            )

    conn.commit()
    return conn


def main():
    s1 = load_source1()
    s2 = load_source2()
    s3 = load_source3()

    print(f"Loaded: {len(s1)} naukri rows, {len(s2)} gig_worker rows, {len(s3)} cbnexus rows")

    clusters = match_people(s1, s2, s3)
    print(f"Merged into {len(clusters)} unique people")

    conn = build_database(clusters)

    # sanity check: show a few multi-source people to prove matching worked
    cur = conn.cursor()
    cur.execute("""
        SELECT p.person_id, p.canonical_name, p.match_confidence, GROUP_CONCAT(s.source_name)
        FROM people p JOIN source_records s ON p.person_id = s.person_id
        GROUP BY p.person_id
        HAVING COUNT(DISTINCT s.source_name) > 1
        LIMIT 10
    """)
    print("\nSample people matched across multiple sources:")
    for row in cur.fetchall():
        print(" ", row)

    conn.close()
    print(f"\nDatabase written to {DB_PATH}")


if __name__ == "__main__":
    main()
