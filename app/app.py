"""
app.py - Task 3: mini audio collection app

Two pages:
  GET  /              -> submission form (name, phone, record or upload audio)
  POST /submit        -> saves the audio, extracts properties, writes to DB
  GET  /submissions   -> lists all submissions with a play button + properties

Run with:  python app.py
Then open: http://localhost:5000
"""

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from pydub import AudioSegment

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "db" / "consultbae.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extract_audio_properties(filepath):
    """
    Uses pydub (backed by ffmpeg) to read whatever format the browser
    or user gave us - webm, ogg, mp3, wav, m4a, all work the same way.

    Returns duration (sec), sample rate (Hz), bitrate (kbps), and
    loudness in dBFS (decibels relative to full scale - 0 dB is the
    loudest possible, negative numbers are quieter; this is the
    standard way to measure loudness without needing a reference level).
    """
    audio = AudioSegment.from_file(filepath)

    duration_sec = len(audio) / 1000.0
    sample_rate_hz = audio.frame_rate
    file_size_bytes = os.path.getsize(filepath)
    bitrate_kbps = (file_size_bytes * 8) / duration_sec / 1000 if duration_sec > 0 else 0
    loudness_db = audio.dBFS

    # Bonus: rough noise/quality estimate.
    # We compare peak loudness to average loudness (crest factor) as a
    # crude signal-quality proxy: recordings that are extremely quiet
    # (very negative dBFS) or clipped (dBFS near 0) are flagged as
    # lower quality. This is a simple heuristic, not a real audio
    # quality metric - documented as a judgement call.
    if loudness_db == float("-inf"):
        quality_estimate = "silent / no signal detected"
    elif loudness_db > -3:
        quality_estimate = "possibly clipped (too loud)"
    elif loudness_db < -40:
        quality_estimate = "very quiet, possible noise/quality issue"
    else:
        quality_estimate = "acceptable range"

    return {
        "duration_sec": round(duration_sec, 2),
        "sample_rate_hz": sample_rate_hz,
        "bitrate_kbps": round(bitrate_kbps, 2),
        "loudness_db": round(loudness_db, 2) if loudness_db != float("-inf") else None,
        "quality_estimate": quality_estimate,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    audio_file = request.files.get("audio")

    if not name or not phone or not audio_file:
        return "Missing name, phone, or audio file", 400

    # save with a unique filename so simultaneous submissions never collide
    ext = os.path.splitext(audio_file.filename)[1] or ".webm"
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / unique_filename
    audio_file.save(filepath)

    try:
        props = extract_audio_properties(filepath)
    except Exception as e:
        return f"Could not process audio file: {e}", 400

    # try to link this submission to an existing person by phone number
    # (reusing the same normalization approach as Task 1)
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT person_id FROM people WHERE canonical_phone = ?", (digits,))
    row = cur.fetchone()
    person_id = row["person_id"] if row else None

    cur.execute(
        """
        INSERT INTO audio_submissions
            (person_id, name, phone, file_path, duration_sec, sample_rate_hz,
             bitrate_kbps, loudness_db, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person_id, name, phone, unique_filename,
            props["duration_sec"], props["sample_rate_hz"],
            props["bitrate_kbps"], props["loudness_db"],
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("submissions"))


@app.route("/submissions")
def submissions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audio_submissions ORDER BY submitted_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return render_template("submissions.html", submissions=rows)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
