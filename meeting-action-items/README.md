# Meeting → Action Items

A web app that turns a raw meeting transcript into a structured table of
action items — owner, task, deadline, and priority — with a simple
dark-themed UI. Runs **100% locally, no API key required**.

![status](https://img.shields.io/badge/runs-offline-brightgreen)

## 1. Problem Statement

Meeting notes are full of commitments ("I'll send the deck by Friday",
"Priya will own the timeline") that get lost the moment the call ends.
This project extracts those commitments automatically into a clean,
structured table — the kind of thing you'd actually want your team to use
after every standup or client call.

## 2. Architecture

```
Transcript text
      │
      ▼
┌─────────────────┐
│  parse_transcript │  splits into (speaker, sentence) pairs
└─────────────────┘
      │
      ▼
┌─────────────────┐
│  ACTION_REGEX     │  filters to sentences containing commitment
│  (will, needs to,  │  language ("will", "needs to", "can you", ...)
│  can you, ...)     │
└─────────────────┘
      │
      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  extract_owner    │    │ extract_deadline  │    │  priority        │
│  (named subject /  │    │  (regex + relative │    │  keyword match   │
│   speaker fallback)│    │   date resolution) │    │  (urgent/no rush) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
      │                       │                       │
      └───────────────────────┴───────────────────────┘
                              ▼
                    Structured Action Item
                 {owner, task, deadline, priority}
                              │
                              ▼
                    Flask JSON API → Web UI table
```

## 3. Why Rule-Based Instead of an LLM Call?

It would be trivial to pipe the transcript into an LLM and ask for JSON
back — and that version is included too (`llm_extractor.py`). But as a
**resume project**, a pure LLM wrapper doesn't show much of your own
engineering, since all the interesting work happens inside a prompt you
can't fully explain or debug.

This project's main path instead uses **transparent, debuggable logic**:
regex pattern matching + light heuristics for owner/deadline/priority
extraction. Every decision the pipeline makes can be traced back to a
specific rule.

| | Rule-based (`extractor.py`, default) | LLM-based (`llm_extractor.py`, optional) |
|---|---|---|
| Cost | Free | API cost per call |
| Latency | Instant | Network round-trip |
| Explainability | Every extraction traces to a specific regex/rule | Harder to say exactly why a given output appeared |
| Setup | Zero — works out of the box | Requires an API key (OpenAI or Cohere) |
| Weakness | Misses paraphrased/implicit commitments ("we probably need someone to own this") | Handles natural language well, but costs money and can hallucinate |

**Good interview answer for "why not just use an LLM":** *"I built the
rule-based version first as a transparent, zero-cost baseline I could
fully explain. I also implemented an LLM-based version to compare recall
on more natural, implicit phrasing. In production, I'd likely run the
cheap rule-based pass first and only fall back to the LLM for sentences
the rules don't confidently classify — that balances cost and quality."*

## 4. What's in the Box

```
meeting-action-items/
├── README.md
├── requirements.txt
├── app.py                    # Flask server (routes: / and /api/extract)
├── extractor.py               # the core rule-based extraction engine
├── llm_extractor.py           # OPTIONAL: OpenAI/Cohere-based extraction for comparison
├── transcribe.py              # OPTIONAL: turns audio into transcript text (Whisper)
├── test_extractor.py          # unit tests for the extraction logic
├── sample_data/
│   └── sample_transcript.txt  # a realistic sample meeting transcript
├── templates/
│   └── index.html             # the UI
└── static/
    ├── style.css
    └── app.js
```

## 5. How to Run

```bash
pip install -r requirements.txt
python app.py
```
Then open **http://localhost:5000** in your browser.

- Paste a transcript (or click "Load sample transcript")
- Set the meeting date (used to resolve "next week", "Friday", etc. into
  actual dates)
- Click "Extract action items"

### Run the tests
```bash
python test_extractor.py
```

### Optional: transcribe audio first
If you have an actual meeting recording instead of text:
```bash
pip install openai-whisper          # local mode, needs ffmpeg + downloads model weights
python transcribe.py meeting.mp3 --mode local --output transcript.txt
```
or, using OpenAI's hosted API instead of running Whisper locally:
```bash
pip install openai
export OPENAI_API_KEY="sk-..."
python transcribe.py meeting.mp3 --mode api --output transcript.txt
```
Then paste `transcript.txt`'s contents into the web UI.

### Optional: compare against the LLM-based extractor
```bash
pip install openai   # or: pip install cohere
export OPENAI_API_KEY="sk-..."      # or COHERE_API_KEY
python llm_extractor.py sample_data/sample_transcript.txt openai
```

## 6. How the Extraction Logic Works

1. **Parse** — splits the transcript into `(speaker, sentence)` pairs,
   supporting the common `"Name: sentence"` transcript format.
2. **Filter** — keeps only sentences containing commitment language
   (`will`, `needs to`, `should`, `can you`, `let's`, ...), while
   excluding common non-actionable openers (`let's get started`,
   `let's discuss`, `do you think`, ...).
3. **Extract owner** — priority order:
   - a known meeting participant's name mentioned in the sentence
   - a capitalized subject directly before an action verb (`"Priya will
     take care of it"` → Priya, even if Priya never spoke)
   - first-person commitments (`"I'll handle it"`) → attributed to the speaker
   - fallback → the speaker, or `"Unassigned"` if no speaker is known
4. **Extract deadline** — regex for explicit dates (`March 5th`, `5/12`)
   and relative phrases (`tomorrow`, `next Friday`, `EOD`, `in 3 days`),
   resolved into a concrete date using the meeting date as the reference
   point.
5. **Assign priority** — `High` if urgency keywords appear (`urgent`,
   `ASAP`, `critical`, `blocker`); `Low` if de-prioritizing language
   appears (`no rush`, `whenever`); otherwise `Medium`.

## 7. Known Limitations (be ready to discuss these)

- **Sentence-level context only** — priority/urgency mentioned in a
  *different* sentence from the commitment itself won't be picked up
  (e.g., "This is urgent." followed by a separate "I'll take care of
  it." on its own won't inherit the urgency). A production version would
  window a few sentences of context together.
- **"Can you...?" attribution** — currently attributes the *asker* as
  owner, not the person being asked, since the system can't always tell
  who ultimately agrees to the task. A fix would look at the *next*
  speaker's response for confirmation ("Sure, I'll do it").
- **English only, no accents for name variants** — the name-detection
  heuristic assumes standard capitalization and doesn't handle nicknames
  or multiple people with the same first name.
- **Regex misses heavily paraphrased commitments** — "we probably ought
  to think about handling that eventually" won't be caught, whereas an
  LLM-based approach likely would (see `llm_extractor.py`).
- **No conversation-level deduplication** — if the same task is
  mentioned twice, it will show up as two rows.

Being able to name these limitations *unprompted* in an interview is a
strong signal — it shows you understand your own system's boundaries
rather than overselling it.

## 8. How This Helps in Practice

Realistically deployed, this would sit behind a "Sync your meeting notes"
button in a tool like Slack, Notion, or a calendar app: transcript comes
in (from Zoom/Meet auto-transcription, or Whisper), action items get
extracted, and each owner gets a follow-up ping with their task and
deadline — closing the loop that usually gets lost after a meeting ends.

## 9. Likely Interview Questions & How to Answer Them

**Q: Why regex/rules instead of a proper NLP library like spaCy?**
This was built in a sandbox without internet access to install spaCy's
language models, so I used Python's built-in `re` module. In a real
environment, I'd likely use spaCy for more robust sentence segmentation
and named-entity recognition (to catch names not tied to a "Speaker:"
prefix), and keep the same rule-based philosophy for the actual
owner/deadline/priority logic.

**Q: How would you evaluate this system's accuracy?**
Build a small labeled test set (transcripts with manually annotated
"ground truth" action items), then measure precision (of items
extracted, how many are real) and recall (of real action items, how many
were caught). `test_extractor.py` has a few hand-written cases like this
already — I'd extend that into a proper labeled eval set.

**Q: Why Flask instead of a heavier framework?**
The app is a single form-in, table-out interaction — Flask keeps the
dependency footprint tiny and the whole thing understandable in one
sitting, which matters both for actually shipping something in a weekend
and for being able to explain every line in an interview.

**Q: How would you scale this to real meeting volume?**
Move `/api/extract` behind a proper WSGI server (gunicorn), add request
queuing for the (optional) LLM path since API calls are the bottleneck,
and cache the rule-based results since they're deterministic and cheap
to recompute.

**Q: What would you add with more time?**
- A confidence score per extracted item, and only auto-surface high-confidence ones
- Multi-sentence context windowing (fixes the priority-in-a-different-sentence gap)
- Slack/email integration to actually notify owners
- A proper labeled evaluation set + precision/recall tracking over time
