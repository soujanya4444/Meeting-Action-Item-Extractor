"""
extractor.py
-------------
Rule-based information extraction engine that pulls structured action
items (owner, task, deadline, priority) out of raw meeting transcript text.

WHY RULE-BASED INSTEAD OF AN LLM CALL?
----------------------------------------
It would be trivial to just pipe the transcript into an LLM and ask for
JSON back. That's a valid production approach (see llm_extractor.py for
that version), but as a *resume project* a pure LLM wrapper doesn't show
much of your own engineering - the interesting work happens inside the
prompt, which you can't fully explain or debug.

This module instead does the extraction with transparent, debuggable
logic: regex pattern matching + light heuristics. Every decision the
pipeline makes can be traced back to a specific rule, which means:
  - It works completely offline, with zero API cost and zero latency
  - You can explain exactly why any given item was (or wasn't) extracted
  - It gives you a natural "baseline vs. LLM" comparison to discuss in
    an interview (see README section 7)

PIPELINE
--------
1. Parse transcript into (speaker, sentence) pairs
2. Scan each sentence for "commitment language" (modal verbs / action
   phrases: "will", "needs to", "should", "is going to", "has to", ...)
3. If found, extract:
     - owner:    the speaker, OR a named person mentioned as subject
     - task:     the action clause itself
     - deadline: resolved from date/time phrases ("by Friday", "EOD",
                 "next week", "tomorrow", explicit dates)
     - priority: keyword-based (urgent/ASAP/critical -> High)
4. Return a clean, structured list of action items
"""

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional


# ---------------------------------------------------------------------
# 1. Commitment / action-language patterns
# ---------------------------------------------------------------------
# These phrases signal that a sentence contains a commitment/action item,
# not just general discussion. Ordered roughly by how strong a signal
# they are.
ACTION_PATTERNS = [
    r"\bwill\b",
    r"\bi'?ll\b",
    r"\bneeds? to\b",
    r"\bneeds?\s+\w+\s+to\b",   # e.g. "need someone to", "needs help to"
    r"\bshould\b",
    r"\bhas to\b",
    r"\bhave to\b",
    r"\bis going to\b",
    r"\bare going to\b",
    r"\bmust\b",
    r"\bplan(?:s|ning)? to\b",
    r"\bgoing to\b",
    r"\blet'?s\b",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\baction item\b",
    r"\btodo\b",
    r"\bto[- ]do\b",
]
ACTION_REGEX = re.compile("|".join(ACTION_PATTERNS), re.IGNORECASE)

# Sentences that are questions *about* something (not commitments) or
# pure discussion should usually be filtered out even if a modal verb
# appears, e.g. "will this even work?" is not an action item.
NON_ACTION_HINTS = re.compile(
    r"\b(do you think|i wonder|what if|is it possible|why (would|will|does)|"
    r"let'?s\s+(?:also\s+)?(?:get started|begin|kick off|talk about|discuss|think about))\b",
    re.IGNORECASE,
)

PRIORITY_HIGH = re.compile(
    r"\b(urgent|asap|immediately|critical|high priority|right away|blocker)\b",
    re.IGNORECASE,
)
PRIORITY_LOW = re.compile(
    r"\b(when you get a chance|no rush|low priority|whenever|eventually)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# 2. Deadline phrase -> concrete date resolution
# ---------------------------------------------------------------------
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

EXPLICIT_DATE_PATTERNS = [
    # "March 5", "March 5th", "Mar 5, 2025"
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?\b",
    # "5/12" or "5/12/2025" or "05-12-2025"
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
]
EXPLICIT_DATE_REGEX = re.compile("|".join(EXPLICIT_DATE_PATTERNS), re.IGNORECASE)

RELATIVE_DATE_REGEX = re.compile(
    r"\b(today|tomorrow|tonight|eod|end of day|end of week|eow|"
    r"this week|next week|this month|next month|"
    r"(?:next|this|by)\s+(?:" + "|".join(WEEKDAYS) + r")|"
    r"in\s+\d+\s+(?:day|days|week|weeks))\b",
    re.IGNORECASE,
)


def resolve_relative_date(phrase: str, reference_date: datetime) -> Optional[str]:
    """Turn a relative phrase like 'next friday' into a concrete date
    string, anchored to `reference_date` (the meeting date)."""
    p = phrase.lower().strip()

    if p in ("today",):
        return reference_date.strftime("%Y-%m-%d")
    if p in ("tomorrow",):
        return (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")
    if p in ("tonight", "eod", "end of day"):
        return reference_date.strftime("%Y-%m-%d") + " (EOD)"
    if p in ("end of week", "eow", "this week"):
        days_to_friday = (4 - reference_date.weekday()) % 7
        return (reference_date + timedelta(days=days_to_friday)).strftime("%Y-%m-%d")
    if p == "next week":
        days_to_next_monday = (7 - reference_date.weekday()) % 7 or 7
        return (reference_date + timedelta(days=days_to_next_monday)).strftime("%Y-%m-%d")
    if p in ("this month",):
        return reference_date.strftime("%Y-%m") + " (this month)"
    if p in ("next month",):
        year = reference_date.year + (1 if reference_date.month == 12 else 0)
        month = 1 if reference_date.month == 12 else reference_date.month + 1
        return f"{year:04d}-{month:02d} (next month)"

    m = re.match(r"in\s+(\d+)\s+(day|days|week|weeks)", p)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(days=n) if "day" in unit else timedelta(weeks=n)
        return (reference_date + delta).strftime("%Y-%m-%d")

    m = re.match(r"(next|this|by)\s+(" + "|".join(WEEKDAYS) + r")", p)
    if m:
        modifier, weekday_name = m.group(1), m.group(2)
        target_weekday = WEEKDAYS.index(weekday_name)
        days_ahead = (target_weekday - reference_date.weekday()) % 7
        if modifier == "next" or (days_ahead == 0 and modifier != "this"):
            days_ahead += 7 if days_ahead == 0 else 0
            if modifier == "next":
                days_ahead += 7 if days_ahead < 7 else 0
        if days_ahead == 0:
            days_ahead = 7 if modifier == "next" else 0
        return (reference_date + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    return None


def extract_deadline(sentence: str, reference_date: datetime) -> Optional[str]:
    explicit = EXPLICIT_DATE_REGEX.search(sentence)
    if explicit:
        return explicit.group(0)

    relative = RELATIVE_DATE_REGEX.search(sentence)
    if relative:
        resolved = resolve_relative_date(relative.group(0), reference_date)
        return resolved or relative.group(0)

    return None


# ---------------------------------------------------------------------
# 3. Owner extraction
# ---------------------------------------------------------------------
NAMED_SUBJECT_REGEX = re.compile(
    r"\b([A-Z][a-z]+)\s+(?:will|is going to|are going to|needs to|should|has to|must)\b"
)

# common capitalized sentence-openers that are NOT names, to avoid false
# positives like "We will..." / "This needs to..."
NON_NAME_WORDS = {
    "we", "i", "this", "that", "they", "he", "she", "it", "you",
    "there", "here", "someone", "somebody", "everyone", "everybody",
}


def extract_owner(sentence: str, speaker: Optional[str], known_names: List[str]) -> str:
    """
    Heuristic priority order:
      1. An explicit named person mentioned right before the action verb
         ("Sarah will send the deck") - checked against known participant names
      2. A capitalized subject directly before an action verb, even if not
         a known speaker ("Priya will take care of it")
      3. First-person commitment ("I'll handle it") -> the speaker
      4. Fallback -> the speaker (most common case: someone stating their
         own task in a meeting)
    """
    for name in known_names:
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        if pattern.search(sentence):
            return name

    subject_match = NAMED_SUBJECT_REGEX.search(sentence)
    if subject_match:
        candidate = subject_match.group(1)
        if candidate.lower() not in NON_NAME_WORDS:
            return candidate

    if re.search(r"\bi'?ll\b|\bi will\b|\bi need to\b|\bi'?m going to\b", sentence, re.IGNORECASE):
        return speaker or "Unknown"

    return speaker or "Unassigned"


# ---------------------------------------------------------------------
# 4. Data model
# ---------------------------------------------------------------------
@dataclass
class ActionItem:
    owner: str
    task: str
    deadline: Optional[str]
    priority: str
    source_line: str


# ---------------------------------------------------------------------
# 5. Transcript parsing
# ---------------------------------------------------------------------
SPEAKER_LINE_REGEX = re.compile(r"^\s*([A-Z][a-zA-Z .]{1,30}):\s*(.+)$")


def parse_transcript(text: str):
    """
    Parses transcript lines. Supports the common meeting-transcript
    format: 'Speaker Name: sentence sentence sentence.'
    Falls back to treating a whole line as speaker-less text if it
    doesn't match that format.
    Returns list of (speaker_or_None, sentence) tuples, split further
    on sentence boundaries.
    """
    results = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = SPEAKER_LINE_REGEX.match(line)
        if match:
            speaker, content = match.group(1).strip(), match.group(2).strip()
        else:
            speaker, content = None, line

        # naive sentence split (good enough for meeting notes)
        sentences = re.split(r"(?<=[.!?])\s+", content)
        for s in sentences:
            s = s.strip()
            if s:
                results.append((speaker, s))
    return results


def extract_known_names(parsed_lines) -> List[str]:
    names = set()
    for speaker, _ in parsed_lines:
        if speaker:
            names.add(speaker)
    return sorted(names, key=len, reverse=True)  # longest-first avoids partial-name collisions


# ---------------------------------------------------------------------
# 6. Main extraction function
# ---------------------------------------------------------------------
def extract_action_items(transcript_text: str, meeting_date: Optional[str] = None) -> List[dict]:
    reference_date = datetime.today()
    if meeting_date:
        try:
            reference_date = datetime.strptime(meeting_date, "%Y-%m-%d")
        except ValueError:
            pass

    parsed = parse_transcript(transcript_text)
    known_names = extract_known_names(parsed)

    items: List[ActionItem] = []
    for speaker, sentence in parsed:
        if NON_ACTION_HINTS.search(sentence):
            continue
        if not ACTION_REGEX.search(sentence):
            continue

        owner = extract_owner(sentence, speaker, known_names)
        deadline = extract_deadline(sentence, reference_date)

        if PRIORITY_HIGH.search(sentence):
            priority = "High"
        elif PRIORITY_LOW.search(sentence):
            priority = "Low"
        else:
            priority = "Medium"

        items.append(ActionItem(
            owner=owner,
            task=sentence,
            deadline=deadline,
            priority=priority,
            source_line=f"{speaker}: {sentence}" if speaker else sentence,
        ))

    return [asdict(item) for item in items]


if __name__ == "__main__":
    # quick manual smoke test
    sample = """
    Sarah: I'll send the updated design deck to the client by Friday.
    James: Sounds good. We should also schedule a follow-up call next week.
    Priya: Can you review the API docs? It's kind of urgent, we're blocked.
    James: Sure, I'll do it by tomorrow.
    Sarah: Let's also think about whether this even makes sense long term.
    """
    for item in extract_action_items(sample, meeting_date="2025-06-02"):
        print(item)
