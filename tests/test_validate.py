import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))

VALID_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events",
}
VALID_KEYS = {"intent", "date", "time", "place"}


def validate(obj):
    if not isinstance(obj, dict) or set(obj.keys()) != VALID_KEYS:
        return False
    if obj["intent"] not in VALID_INTENTS:
        return False
    for key in ("date", "time", "place"):
        if obj[key] is not None and not isinstance(obj[key], str):
            return False
    return True


def test_valid_object_passes():
    obj = {"intent": "alarm_set", "date": "tomorrow", "time": "seven am", "place": None}
    assert validate(obj) is True


def test_missing_key_fails():
    obj = {"intent": "alarm_set", "date": "tomorrow", "time": "seven am"}
    assert validate(obj) is False


def test_bad_intent_fails():
    obj = {"intent": "make_coffee", "date": None, "time": None, "place": None}
    assert validate(obj) is False


def test_non_string_slot_fails():
    obj = {"intent": "alarm_set", "date": 5, "time": None, "place": None}
    assert validate(obj) is False
