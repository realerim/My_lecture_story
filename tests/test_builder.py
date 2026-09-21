from lecture_note.notes.builder import build_sections


def test_empty_inputs_returns_empty():
    assert build_sections([], []) == []


def test_no_screen_events_puts_all_transcript_in_one_section():
    segments = [
        {"start": 1.0, "end": 3.0, "text": "hello"},
        {"start": 4.0, "end": 6.0, "text": "world"},
    ]
    sections = build_sections([], segments)
    assert len(sections) == 1
    assert sections[0].image is None
    assert sections[0].raw_text == "hello world"


def test_transcript_split_across_screen_changes():
    events = [
        {"ts": 0, "image": "screenshots/a.png"},
        {"ts": 10, "image": "screenshots/b.png"},
        {"ts": 25, "image": "screenshots/c.png"},
    ]
    segments = [
        {"start": 1, "end": 3, "text": "intro"},
        {"start": 5, "end": 9, "text": "more intro"},
        {"start": 12, "end": 15, "text": "second slide"},
        {"start": 30, "end": 33, "text": "third slide"},
    ]
    sections = build_sections(events, segments)

    assert [s.start for s in sections] == [0, 10, 25]
    assert [s.end for s in sections] == [10, 25, None]
    assert sections[0].raw_text == "intro more intro"
    assert sections[1].raw_text == "second slide"
    assert sections[2].raw_text == "third slide"


def test_transcript_before_first_screen_event_is_absorbed_into_first_section():
    events = [{"ts": 5, "image": "screenshots/a.png"}]
    segments = [{"start": 0, "end": 2, "text": "before first screenshot"}]
    sections = build_sections(events, segments)

    assert len(sections) == 1
    assert sections[0].raw_text == "before first screenshot"


def test_screen_events_are_sorted_before_bucketing():
    events = [
        {"ts": 10, "image": "screenshots/b.png"},
        {"ts": 0, "image": "screenshots/a.png"},
    ]
    sections = build_sections(events, [])
    assert [s.image for s in sections] == ["screenshots/a.png", "screenshots/b.png"]


def test_section_with_no_matching_transcript_has_empty_raw_text():
    events = [{"ts": 0, "image": "screenshots/a.png"}, {"ts": 5, "image": "screenshots/b.png"}]
    sections = build_sections(events, [])
    assert sections[0].raw_text == ""
    assert sections[1].raw_text == ""
