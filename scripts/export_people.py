"""
export_people.py
Exports the 'people' table from consultbae.db into a flat JSON file
that our n8n automation can fetch over HTTP and check new records against.

Why this exists (design note for the stuck log / defense):
n8n Cloud runs on n8n's own servers, not on this laptop, so it cannot
open a local SQLite file directly. Hosting a JSON snapshot on GitHub
(a public raw URL) is a simple stand-in for what would be a real API
endpoint in production. The automation demonstrates the same duplicate-
detection LOGIC either way -- only the data-access method differs.

Run with:  python scripts/export_people.py
Produces:  data/people_export.json
"""

import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "consultbae.db"
OUT_PATH = BASE_DIR / "data" / "people_export.json"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT person_id, canonical_name, canonical_email, canonical_phone, canonical_city FROM people")
    people = [dict(row) for row in cur.fetchall()]
    conn.close()

    OUT_PATH.write_text(json.dumps(people, indent=2))
    print(f"Exported {len(people)} people to {OUT_PATH}")


if __name__ == "__main__":
    main()
