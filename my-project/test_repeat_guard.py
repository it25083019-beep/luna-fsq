"""Tests for the companion repeat guard.

The guard is only useful across requests, so these also pin down that the
state it relies on is not stripped when the brain is saved.
"""
from __future__ import annotations

from luna_service import (
    RECENT_LINE_MEMORY,
    _REPEAT_NUDGES,
    _avoid_repeat_dialogue,
    _dialogue_similar,
    save_user_brain,
)

LINE = "今日の気分「疲れ」を残したよ。無理しないでね。"


def fresh():
    return {"user_display_name": "ユウ", "gender": "female"}


def test_first_line_passes_through():
    user = fresh()
    assert _avoid_repeat_dialogue(user, LINE) == LINE
    assert user["recent_companion_lines"] == [LINE]


def test_immediate_repeat_is_replaced():
    user = fresh()
    _avoid_repeat_dialogue(user, LINE)
    second = _avoid_repeat_dialogue(user, LINE)
    assert second != LINE
    assert "ユウ" in second


def test_repeats_do_not_alternate_back_to_the_original():
    """A nudge must not displace the line it was covering for."""
    user = fresh()
    said = [_avoid_repeat_dialogue(user, LINE) for _ in range(4)]
    assert said[0] == LINE
    # None of the follow-ups may be the original line again.
    assert LINE not in said[1:], said
    # And the nudges themselves must differ from each other.
    assert len(set(said[1:])) == len(said[1:]), said


def test_nudges_rotate_through_the_pool():
    user = fresh()
    _avoid_repeat_dialogue(user, LINE)
    seen = {_avoid_repeat_dialogue(user, LINE) for _ in range(len(_REPEAT_NUDGES))}
    assert len(seen) == len(_REPEAT_NUDGES), seen


def test_a_genuinely_new_line_is_untouched():
    user = fresh()
    _avoid_repeat_dialogue(user, LINE)
    other = "800円の支出、記録したよ。今週の残りは意識しておこうね。"
    assert _avoid_repeat_dialogue(user, other) == other


def test_memory_is_bounded():
    user = fresh()
    for i in range(RECENT_LINE_MEMORY + 5):
        _avoid_repeat_dialogue(user, f"別の話題{i}についてメモしておいたよ。")
    assert len(user["recent_companion_lines"]) == RECENT_LINE_MEMORY


def test_guard_state_survives_a_save():
    """save_user_brain strips ephemeral flags; this must not be one of them."""
    user = fresh()
    _avoid_repeat_dialogue(user, LINE)
    payload = dict(user)
    try:
        save_user_brain("__test_repeat_guard__", payload)
    except Exception:
        # No DB in this environment; the strip step runs before any write.
        pass
    assert payload.get("recent_companion_lines"), payload


def test_corrupt_state_does_not_crash():
    user = fresh()
    user["recent_companion_lines"] = [None, "", LINE]
    user["repeat_nudge_i"] = "not a number"
    out = _avoid_repeat_dialogue(user, LINE)
    assert out and out != LINE


def test_similarity_needs_real_overlap():
    assert _dialogue_similar("おはよう", "おはよう")
    assert not _dialogue_similar("おはよう", "こんばんは、今日はどうだった？")
    assert not _dialogue_similar("", "何か")


if __name__ == "__main__":
    test_first_line_passes_through()
    test_immediate_repeat_is_replaced()
    test_repeats_do_not_alternate_back_to_the_original()
    test_nudges_rotate_through_the_pool()
    test_a_genuinely_new_line_is_untouched()
    test_memory_is_bounded()
    test_guard_state_survives_a_save()
    test_corrupt_state_does_not_crash()
    test_similarity_needs_real_overlap()
    print("ALL repeat guard tests OK")
