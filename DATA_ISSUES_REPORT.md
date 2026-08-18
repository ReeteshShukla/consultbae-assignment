# Task 4 — Data Issues Report

All issues below were found by direct inspection of the 3 source files plus
verification against the actual ingested output (`scripts/ingest.py` /
`db/consultbae.db`). For each issue: what it is, an example, and what the
pipeline does about it.

## 1. No single ID is common across all 3 files
- Source 1 (Naukri) has email + phone
- Source 2 (gig workers) has email only
- Source 3 (CBNexus) has phone only
**What we did**: matched Source1↔Source2 on normalized email, and
Source1↔Source3 on normalized phone, so Source3 links to Source2 only
transitively through Source1. Any record we couldn't match on email/phone
falls back to a fuzzy name+city match and is explicitly flagged
`match_confidence = 'fuzzy'` in the `people` table rather than being merged
silently.

## 2. Phone numbers are formatted inconsistently
Same person, different formats across rows: `9000000268`,
`+91-9000000131`, `919000000231`, `09000000287`.
**What we did**: stripped all non-digit characters and kept the last 10
digits, which normalizes country code and leading-zero variants to one
canonical form (`normalize.py::normalize_phone`).

## 3. Emails are case-inconsistent
Source 2's `email_id` column mixes `isha.chopra95@mailtest.example.org`
and `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`.
**What we did**: lowercased and trimmed every email before comparing
(`normalize_email`).

## 4. Same person appears twice within a single source file
Two distinct examples found:
- Source 1 has **Nikhil Chopra** twice with two different email addresses
  (`nikhil.chopra70@...` and `alt.nikhil.chopra70@...`) but the identical
  phone number — caught by the phone match.
- Source 1 has **"R. Verma"** and **"Rohit Verma"** as two separate rows
  with identical email and phone — a name-spelling variant of the same
  person, caught despite the name mismatch because email/phone matched.

**What we did**: since matching runs on email/phone rather than name, both
cases correctly collapsed into one person record. Verified directly against
the database (see person_id 24 and 26 in the merged output).

## 5. City names are inconsistent
`NOIDA`, `Noida ` (trailing space), `noida` all appear; `Gurgaon` and
`Gurugram` are used interchangeably (same city, officially renamed).
**What we did**: lowercase + trim, and explicitly merge `gurgaon`/`gurugram`
into one value. We deliberately did **not** auto-merge `Delhi` / `New Delhi`
/ `Delhi NCR` — these could reasonably refer to different scopes (city vs.
metro region), so collapsing them automatically would be a bigger judgment
call than the phone/city normalization above. This is flagged here rather
than resolved silently.

## 6. A row is shifted/malformed in source2
One row has its `skill_tags` value sitting in the `email_id` column
instead: `"react, javascript, mysql", ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,
Isha Chopra, 1406/hr, Pune, active`. This also duplicates a valid Isha
Chopra row elsewhere in the same file.
**What we did**: the ingestion script checks for `"@"` in the email field
and skips rows that fail this check, since we cannot reliably reconstruct
the correct column alignment for a single malformed row without guessing.

## 7. A fully blank row exists in source2
One row is empty (all commas, no data).
**What we did**: `load_csv()` filters out any row where every field is
blank before processing.

## 8. A repeated header row appears mid-file in source3
The literal header (`Name, Phone Number, ...`) reappears as a data row
partway through `source3_cbnexus_contacts.csv`.
**What we did**: `load_source3()` explicitly skips any row where
`Name == "Name"`.

## 9. The same numeric field mixes two different units
- Source 1 `Current CTC`: most values are large integers like `417964`
  (annual rupees), but some are small decimals like `4.2`, `8.3`, `11.2`
  — almost certainly the same figure expressed in **lakhs** (4.2 lakh =
  ₹420,000), not annual rupees.
- Source 2 `rate`: mixes `.../hr` and `...k/month` in the same column.
**What we did**: `parse_ctc()` treats any value under 1000 as lakhs and
multiplies by 100,000; `parse_rate()` converts hourly rates to an estimated
monthly figure (assuming ~160 working hours/month) and `k/month` values to
plain rupees. **Both conversions are judgment calls, not certainties** —
flagged here explicitly rather than presented as verified fact.

## 10. Boolean/status-like fields are encoded inconsistently
- Source 3 `Verified`: appears as `Y`, `N`, `yes`, `No`, `Yes`.
- Source 2 `status`: appears as `Active`, `active`, `ACTIVE`, `Inactive`,
  and — importantly — `paused`, which is a genuinely different state, not
  just a casing variant of Active/Inactive.
**What we did**: `normalize_verified()` maps all Verified spellings to a
real boolean. `normalize_status()` only lowercases/trims — it deliberately
keeps `paused` as its own distinct value rather than collapsing it into
Active or Inactive, since that would lose real information.

## 11. Skill tags are inconsistently cased
`REST APIs` vs `rest apis`, `Web Scraping` vs `web scraping`, etc.
**What we did**: `normalize_skills()` lowercases and trims each
comma-separated skill before use.

## 12. Applied Date uses at least 4 different formats in the same column
Verified directly against the raw file — the `Applied Date` column in
Source 1 mixes `DD-MM-YYYY` (`24-07-2026`), `YYYY-MM-DD` (`2026-08-08`),
`D Mon YYYY` (`7 Jul 2026`), and `MM/DD/YYYY` (`07/13/2026`) in the same
column. The `MM/DD/YYYY` values are genuinely ambiguous against
`DD-MM-YYYY` whenever both day and month are ≤12 (e.g. `07/03/2026` could
mean 7 March or 3 July).
**What we did**: left this field as a raw string rather than attempting to
parse it, since a wrong guess on the ambiguous cases would silently corrupt
data — flagging the ambiguity here is more honest than a confident-looking
but potentially wrong parsed date.

---

**Summary**: 12 distinct categories of data quality issues found across the
3 files, covering identity resolution, formatting inconsistency, unit
mixing, malformed rows, and ambiguous date parsing. Where a fix required a
judgment call (CTC/rate unit conversion, city normalization scope, fuzzy
match confidence), that judgment is explicitly flagged in the data rather
than silently applied.
