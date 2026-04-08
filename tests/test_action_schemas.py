# -*- coding: utf-8 -*-
from sokol.action_schemas import coerce_action_dict, validate_llm_action


def test_validate_llm_action_ok():
    raw = {"type": "launch_app", "target": "notepad", "params": {}}
    out, err = validate_llm_action(raw)
    assert err is None
    assert out["type"] == "launch_app"


def test_validate_llm_action_rejects_empty_type():
    out, err = validate_llm_action({"type": "", "target": "x"})
    assert out is None
    assert err


def test_coerce_action_dict_fills_params():
    d = coerce_action_dict({"type": "help"})
    assert d["params"] == {}
