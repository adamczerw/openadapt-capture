"""Tests for stripping the keyboard stop sequence from loaded recordings."""

from openadapt_capture.capture import _strip_trailing_stop_sequence
from openadapt_capture.events import KeyDownEvent, KeyUpEvent, MouseMoveEvent

STOP_SEQUENCES = [["ctrl", "ctrl", "ctrl"], list("oa.stop")]


def _ctrl_presses(n: int, start: float = 10.0) -> list:
    events = []
    for i in range(n):
        t = start + i
        events.append(KeyDownEvent(timestamp=t, key_name="ctrl_l", canonical_key_name="ctrl"))
        events.append(KeyUpEvent(timestamp=t + 0.1, key_name="ctrl_l", canonical_key_name="ctrl"))
    return events


def _typed(text: str, start: float = 10.0) -> list:
    events = []
    for i, char in enumerate(text):
        t = start + i
        events.append(KeyDownEvent(timestamp=t, key_char=char))
        events.append(KeyUpEvent(timestamp=t + 0.1, key_char=char))
    return events


MOVE = MouseMoveEvent(timestamp=1.0, x=10, y=20)


def test_strips_trailing_ctrl_sequence():
    events = [MOVE, *_ctrl_presses(3)]
    assert _strip_trailing_stop_sequence(events, STOP_SEQUENCES) == [MOVE]


def test_strips_trailing_typed_stop_string():
    events = [MOVE, *_typed("oa.stop")]
    assert _strip_trailing_stop_sequence(events, STOP_SEQUENCES) == [MOVE]


def test_keeps_incomplete_sequence():
    events = [MOVE, *_ctrl_presses(2)]
    assert _strip_trailing_stop_sequence(events, STOP_SEQUENCES) == events


def test_keeps_key_block_with_extra_keys():
    # Task keystrokes directly before the stop sequence form one trailing key
    # block that does not equal a stop sequence, so nothing is removed.
    events = [MOVE, *_typed("a"), *_ctrl_presses(3, start=20.0)]
    assert _strip_trailing_stop_sequence(events, STOP_SEQUENCES) == events


def test_keeps_sequence_not_at_end():
    events = [*_ctrl_presses(3), MOVE]
    assert _strip_trailing_stop_sequence(events, STOP_SEQUENCES) == events


def test_empty_and_no_keys():
    assert _strip_trailing_stop_sequence([], STOP_SEQUENCES) == []
    assert _strip_trailing_stop_sequence([MOVE], STOP_SEQUENCES) == [MOVE]
