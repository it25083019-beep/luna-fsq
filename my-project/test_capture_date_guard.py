"""The model used to invent dates, filing today's spending under a past year."""
from datetime import date, timedelta

from chat_life_capture import _merge_updates, _plausible_date

TODAY = date(2026, 9, 2)


def test_hallucinated_year_is_replaced_with_today():
    hints = {"spend": {"amount": 800, "note": "コンビニ", "date": TODAY.isoformat()}}
    llm = {"spend": {"amount": 800, "note": "コンビニ", "date": "2024-07-27"}}
    out = _merge_updates(hints, llm, today=TODAY)
    assert out["spend"]["date"] == TODAY.isoformat()
    assert out["spend"]["amount"] == 800


def test_nearby_date_from_model_is_kept():
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    hints = {"spend": {"amount": 500, "date": TODAY.isoformat()}}
    llm = {"spend": {"date": yesterday}}
    out = _merge_updates(hints, llm, today=TODAY)
    assert out["spend"]["date"] == yesterday


def test_model_only_spend_with_bad_date_is_corrected():
    out = _merge_updates({}, {"spend": {"amount": 1200, "date": "1999-01-01"}}, today=TODAY)
    assert out["spend"]["date"] == TODAY.isoformat()
    assert out["spend"]["amount"] == 1200


def test_schedule_date_is_guarded_too():
    out = _merge_updates(
        {}, {"schedule_add": {"title": "バイト", "date": "2019-05-05"}}, today=TODAY
    )
    assert out["schedule_add"]["date"] == TODAY.isoformat()


def test_plausible_date_rejects_garbage():
    assert not _plausible_date(None, today=TODAY)
    assert not _plausible_date("not-a-date", today=TODAY)
    assert _plausible_date(TODAY.isoformat(), today=TODAY)
