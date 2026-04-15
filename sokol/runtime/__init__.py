"""Runtime module exports (lazy to avoid import cycles)."""

from importlib import import_module

_EXPORTS = {
    "AgentStateMachine": ("sokol.runtime.state", "AgentStateMachine"),
    "StateTransitionError": ("sokol.runtime.state", "StateTransitionError"),
    "EventBus": ("sokol.runtime.events", "EventBus"),
    "EventListener": ("sokol.runtime.events", "EventListener"),
    "TaskManager": ("sokol.runtime.tasks", "TaskManager"),
    "TaskCancelledError": ("sokol.runtime.tasks", "TaskCancelledError"),
    "Orchestrator": ("sokol.runtime.orchestrator", "Orchestrator"),
    "RuleBasedIntentHandler": ("sokol.runtime.intent", "RuleBasedIntentHandler"),
    "Intent": ("sokol.runtime.intent", "Intent"),
    "IntentRouter": ("sokol.runtime.router", "IntentRouter"),
    "ProposedAction": ("sokol.runtime.router", "ProposedAction"),
    "DecisionSource": ("sokol.runtime.router", "DecisionSource"),
}

__all__ = [
    "AgentStateMachine",
    "StateTransitionError",
    "EventBus",
    "EventListener",
    "TaskManager",
    "TaskCancelledError",
    "Orchestrator",
    "RuleBasedIntentHandler",
    "Intent",
    "IntentRouter",
    "ProposedAction",
    "DecisionSource",
]


def __getattr__(name: str):
    """Lazy-load runtime exports to prevent initialization cycles."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
