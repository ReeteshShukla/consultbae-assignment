# Stuck Log

Three genuine points I got stuck, what I tried, and how I got unstuck.

---

## 1. Audio app wouldn't even start: `ModuleNotFoundError: No module named 'audioop'`

**What happened**: After installing `flask`, `pydub`, and `numpy` and running
`python app.py`, it crashed immediately on `from pydub import AudioSegment`
with a traceback ending in `ModuleNotFoundError: No module named 'audioop'`.
This wasn't a mistake in my code — the app hadn't even reached my logic yet.

**What I searched**: the exact error text,
`ModuleNotFoundError: No module named 'audioop' pydub`. This turned up that
`audioop` is a Python **standard library** module (not something pydub
ships itself), and that Python 3.13 removed it from the standard library
entirely (it was deprecated since 3.11). I was running Python 3.14, which
is new enough that a lot of packages built around the old `audioop`
assumption haven't caught up.

**What I asked AI**: I asked why an error would come from inside pydub's
own internals rather than my code, and whether this was a pydub bug or an
environment issue. It correctly identified this as a known Python
version-compatibility gap, not a bug in my code or in pydub, and pointed me
to `audioop-lts` — a community-maintained backport package published
specifically to restore this module for 3.13+.

**What I rejected**: my first instinct (before searching) was to downgrade
my whole Python installation to 3.11 to sidestep the issue entirely. I
decided against this — it's a much bigger, riskier change (could break
other tools I already have installed) for a problem that had a one-line
fix (`pip install audioop-lts`). Fixing the actual gap was better than
avoiding it by downgrading my whole environment.

**Fix**: `pip install audioop-lts`, then the app ran normally.

---

## 2. n8n's IF node kept routing data to the wrong branch

**What happened**: My duplicate-check logic (a Code node) correctly
computed `is_duplicate: true` for a test submission — I could see this
plainly in the node's JSON output. But the very next node, an IF node
checking that same field, kept sending the data down the **False** branch
instead of True. Nothing looked obviously wrong in the condition I'd set up.

**What I tried first**: re-checking my Code node's logic, assuming the bug
was there, since that felt like the more likely place for a mistake. It
wasn't — the Code node's output was already correct.

**What I asked AI**: I described the exact symptom (correct data going into
the IF node, but the wrong branch firing) and asked what could cause that
specifically in n8n. It pointed out this is usually a **type mismatch**
issue in n8n's condition builder — the field can be internally typed as
Number or String even when the underlying value is a boolean, so
`is_duplicate: true` (boolean) was being compared against `true` typed as
text, which doesn't match.

**What I rejected**: my first fix attempt was to just retype the field
value manually — I tried switching the condition to plain "Fixed" mode
with a literal `true`/`false` toggle. This actually made things worse
because it disconnected the field from the real `is_duplicate` output
entirely, so it stopped reading live data altogether. I reverted that and
instead explicitly changed the condition's data type to **Boolean** with
the **"is true"** operator, which doesn't require a second comparison value
at all and matches the actual data type coming out of the Code node.

**Fix**: set the IF node's condition type explicitly to Boolean, operator
"is true," referencing `{{ $json.is_duplicate }}` directly.

---

## 3. ffmpeg wasn't recognized in PowerShell after installing it

**What happened**: I downloaded and extracted ffmpeg, but running
`ffmpeg -version` in my terminal said it wasn't recognized as a command.
My first download also turned out to be the wrong thing entirely — the
ffmpeg **source code** repository (full of files like `configure` and
`libavcodec`), not a pre-built Windows executable, so there was no `.exe`
to even point to at first.

**What I searched**: "ffmpeg windows download" led me to gyan.dev, a
commonly recommended source for prebuilt Windows ffmpeg binaries — but the
page has several similarly-named download options (git builds vs release
builds, full vs essentials, .7z vs .zip), and I initially grabbed the wrong
one.

**What I asked AI**: after realizing my first download had no `bin` folder
or `.exe` file, I described exactly what the folder contained, and it
recognized this was the source-code build rather than a compiled release,
and pointed me specifically to the "release essentials .zip" option instead.

**What I rejected**: nothing rejected here — this was more a
"didn't know what I didn't know" problem (not realizing ffmpeg downloads
come in several different build types) than a case of multiple valid
approaches. Once I had the right file, the fix was mechanical: extract it,
add its `bin` folder to my Windows PATH environment variable, and restart
my terminal so it would pick up the change.

**Fix**: downloaded `ffmpeg-release-essentials.zip` specifically (not the
source/git builds), extracted it to `C:\`, and added the `bin` subfolder to
my system PATH.
