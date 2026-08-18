"""
test_extractor.py
-------------------
A handful of unit tests for the rule-based extractor. Run with:
    python -m pytest test_extractor.py -v
or simply:
    python test_extractor.py
"""

from extractor import extract_action_items


def test_basic_commitment():
    text = "Sarah: I'll send the report by Friday."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 1
    assert items[0]["owner"] == "Sarah"
    assert items[0]["deadline"] == "2025-06-06"


def test_named_owner_overrides_speaker():
    text = "James: Priya will take care of the deployment."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 1
    assert items[0]["owner"] == "Priya"


def test_high_priority_keyword():
    text = "Sam: This is urgent, we need someone to fix it right away."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 1
    assert items[0]["priority"] == "High"


def test_low_priority_keyword():
    text = "Sam: When you get a chance, could you tidy up the docs? No rush."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 1
    assert items[0]["priority"] == "Low"


def test_non_action_sentence_ignored():
    text = "Sam: Let's get started with today's agenda."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 0


def test_relative_date_next_week():
    # 2025-06-02 is a Monday
    text = "Sam: I'll finish it next week."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert items[0]["deadline"] == "2025-06-09"


def test_relative_date_tomorrow():
    text = "Sam: I'll finish it tomorrow."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert items[0]["deadline"] == "2025-06-03"


def test_no_speaker_prefix_still_parses():
    text = "We should finalize the budget by next Friday."
    items = extract_action_items(text, meeting_date="2025-06-02")
    assert len(items) == 1
    assert items[0]["owner"] == "Unassigned"


if __name__ == "__main__":
    tests = [
        test_basic_commitment,
        test_named_owner_overrides_speaker,
        test_high_priority_keyword,
        test_low_priority_keyword,
        test_non_action_sentence_ignored,
        test_relative_date_next_week,
        test_relative_date_tomorrow,
        test_no_speaker_prefix_still_parses,
    ]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__} -> {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
