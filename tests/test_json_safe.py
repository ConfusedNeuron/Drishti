import math
from src.dashboard.json_safe import clean_json


def test_nan_inf_become_none():
    assert clean_json({"a": float("nan"), "b": [1.0, float("inf")], "c": {"d": -math.inf}}) == \
        {"a": None, "b": [1.0, None], "c": {"d": None}}


def test_passthrough():
    obj = {"x": 1, "y": "s", "z": [1, 2], "w": None, "b": True}
    assert clean_json(obj) == obj
