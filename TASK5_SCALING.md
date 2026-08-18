# Task 5 — Scaling to 5,000 gig workers over one weekend

This is an honest assessment of what breaks in the **current** build
(Flask dev server + SQLite + local disk storage) if we pointed 5,000 real
users at it, and what I'd change before that launch — not a generic
"how to scale" essay.

## What breaks first

**1. The Flask development server itself.**
Flask's built-in server is single-threaded and explicitly warns it isn't
production-ready. With 5,000 people hitting it over a weekend — likely in
bursts around a launch announcement — concurrent requests would queue up
or the server would simply hang. This is the first and most certain
failure point, not a hypothetical one.

**2. SQLite's single-writer limitation.**
SQLite locks the whole database file for writes. Every audio submission
does one INSERT; under real concurrency (multiple people submitting in the
same second), most of those writes would fail with "database is locked"
errors rather than queueing gracefully.

**3. Local disk storage filling up / disappearing.**
Audio files are saved straight to the server's local disk
(`app/uploads/`). At even a modest 1MB per recording, 5,000 submissions is
~5GB — survivable, but the real risk is that this is a single point of
failure: if the server restarts, gets redeployed, or the disk fills past
capacity, submissions are silently lost with no backup.

**4. No upload size or rate limits.**
Nothing currently stops someone from uploading a 500MB file, or the same
person submitting 200 times in a row. Either would degrade the service for
everyone else with zero defense in place today.

## What I'd change before launch

**Storage & uploads**
- Move audio files to object storage (e.g. S3-compatible storage) instead
  of local disk — durable, doesn't depend on one server surviving.
- Add a max file size and max recording duration limit at upload time —
  right now the app trusts every submission blindly.
- Process audio extraction (duration/sample rate/bitrate/loudness)
  asynchronously in a background queue rather than inline during the
  request — a slow ffmpeg call on a big file shouldn't block the whole
  request/response cycle for other users.

**Server & concurrency**
- Replace the Flask dev server with a real WSGI server (e.g. Gunicorn)
  behind a reverse proxy, running multiple worker processes.
- Move from SQLite to a server-based database (Postgres) that handles
  concurrent writes properly instead of file-level locking.

**Failures**
- Right now, a failed upload just shows a raw error to the user with no
  retry path. I'd add client-side retry logic for flaky mobile connections
  (a real concern for gig workers submitting from phones), plus a clear
  "your submission is being processed" state instead of a hard fail.
- Add basic monitoring/alerting so we'd know within minutes if error rates
  spike, rather than finding out from angry workers on Monday.

**Duplicates**
- The current duplicate check (matching against the `people` table by
  phone number) only runs at ingestion time against a static snapshot.
  At scale I'd run this check live against the production database on
  every submission, and decide up front: do we allow one audio submission
  per person, or many? Right now nothing stops one worker from submitting
  50 times — that's a policy decision, not just a technical one, and it
  should be made explicitly before launch rather than discovered after.

**Cost**
- SQLite + local disk is free but doesn't scale — object storage +
  managed Postgres has a real, small, predictable monthly cost that's
  worth paying before a 5,000-person weekend rather than after an outage.
- Audio processing (ffmpeg) is CPU-bound; doing it synchronously on the
  same server handling uploads means compute cost scales badly with
  traffic spikes. Moving it to a queue means we only pay for processing
  capacity we actually need, and it can scale independently of the
  upload-handling servers.

## Honest bottom line
Everything we built works correctly for a demo and a handful of users.
None of it is a fundamentally wrong design — the failure modes above are
exactly what you'd expect from "make it work first, make it scale later,"
which was the right call for a 48-hour assignment. The changes above are
what separates a working demo from something that survives real traffic.
