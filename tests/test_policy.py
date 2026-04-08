# -*- coding: utf-8 -*-
from sokol import policy


class _G:
    _pending_secure_action = None


def test_policy_skips_when_confirmed():
    g = _G()
    action = {"type": "terminal_ps", "target": "dir", "params": {"_security_confirmed": True}}
    assert policy.prepare_security_confirmation(action, g) is None


def test_policy_terminal_intercept():
    g = _G()
    action = {"type": "terminal_cmd", "target": "echo hi", "params": {}}
    r = policy.prepare_security_confirmation(action, g)
    assert r is not None
    assert r[1] == "__CONFIRM_TERMINAL__"
    assert g._pending_secure_action["type"] == "terminal_cmd"


def test_mark_action_confirmed():
    a = policy.mark_action_confirmed({"type": "wifi_passwords", "params": {}})
    assert a["params"]["_security_confirmed"] is True
