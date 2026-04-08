# -*- coding: utf-8 -*-
"""Security policy: confirmations before high-risk tool execution."""
from __future__ import annotations

import copy
import logging
from typing import Any, Optional, Tuple

from .config import CONFIRM_MESSENGER_SEND
from .logging_config import audit_line

_log = logging.getLogger("sokol.policy")

# Return type: None = proceed, or (True, magic_message_for_gui)
SecurityResult = Optional[Tuple[bool, str]]


def _clone_action(action: dict) -> dict:
    try:
        return copy.deepcopy(action)
    except Exception:
        out = dict(action)
        p = out.get("params")
        if isinstance(p, dict):
            out["params"] = dict(p)
        return out


def check_system_action(action_type: str, params: dict) -> bool:
    """
    Check if system action is allowed by security policy
    Returns True if action is safe, False if blocked
    """
    try:
        # Dangerous operations that require confirmation
        dangerous_actions = {
            "delete_files": ["C:\\Windows", "C:\\Windows\\System32", "System32"],
            "format_drive": ["C:", "system"],
            "registry_edit": ["HKEY_LOCAL_MACHINE"],
            "network_scan": ["port", "network"],
            "process_kill": ["system", "critical", "winlogon"]
        }
        
        # Check action type
        if action_type in dangerous_actions:
            for keyword in dangerous_actions[action_type]:
                # Check if dangerous keywords are in params
                for param_value in params.values():
                    if isinstance(param_value, str) and keyword.lower() in param_value.lower():
                        audit_line(f"policy: blocked dangerous {action_type} with keyword: {keyword}")
                        return False
        
        # Basic safety checks passed
        audit_line(f"policy: allowed {action_type}")
        return True
        
    except Exception as e:
        _log.error(f"Policy check error: {e}")
        return False  # Fail safe


def prepare_security_confirmation(action: dict, gui: Any) -> SecurityResult:
    """
    If this action needs user confirmation, stash a copy on gui and return a magic string.
    Caller should return (True, magic) to the UI layer.
    """
    params = action.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    if params.get("_security_confirmed"):
        return None

    atype = (action.get("type") or "").lower()

    if atype in ("terminal_ps", "terminal_cmd"):
        gui._pending_secure_action = _clone_action(action)
        audit_line(f"policy: terminal confirmation required type={atype}")
        return True, "__CONFIRM_TERMINAL__"

    if atype == "wifi_passwords":
        gui._pending_secure_action = _clone_action(action)
        audit_line("policy: wifi passwords confirmation required")
        return True, "__CONFIRM_WIFI__"

    if atype == "messenger_send" and CONFIRM_MESSENGER_SEND:
        gui._pending_secure_action = _clone_action(action)
        audit_line("policy: messenger_send confirmation required")
        return True, "__CONFIRM_MESSENGER__"

    if atype in ("deep_clean", "bulk_delete"):
        gui._pending_secure_action = _clone_action(action)
        audit_line(f"policy: destructive action confirmation required type={atype}")
        return True, "__CONFIRM_DESTRUCTIVE__"

    if atype in ("service_stop", "service_restart") and action.get("target"):
        gui._pending_secure_action = _clone_action(action)
        audit_line(f"policy: service action confirmation type={atype}")
        return True, "__CONFIRM_SERVICE__"

    return None


def mark_action_confirmed(action: dict) -> dict:
    """Return a new action dict with _security_confirmed set."""
    a = _clone_action(action)
    p = a.get("params")
    if not isinstance(p, dict):
        p = {}
        a["params"] = p
    p["_security_confirmed"] = True
    return a
