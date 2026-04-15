"""Formal replay verifier for strict full-graph equality."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sokol.runtime.observability import ExecutionTrace


@dataclass(frozen=True)
class ReplayMismatch:
    """Single mismatch entry in strict replay compare."""

    path: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ReplayVerdict:
    """Replay comparison verdict."""

    status: str
    mismatches: list[ReplayMismatch]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def _canonical_trace(trace: ExecutionTrace) -> dict[str, Any]:
    """Build canonical deterministic graph snapshot from trace."""
    payload = asdict(trace)
    payload.pop("trace_id", None)
    payload.pop("timestamp", None)
    payload.pop("execution_time_seconds", None)
    return payload


def _collect_mismatches(
    expected: Any,
    actual: Any,
    *,
    path: str = "root",
) -> list[ReplayMismatch]:
    if type(expected) is not type(actual):
        return [ReplayMismatch(path=path, expected=expected, actual=actual)]

    if isinstance(expected, dict):
        mismatches: list[ReplayMismatch] = []
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        for missing in sorted(expected_keys - actual_keys):
            mismatches.append(
                ReplayMismatch(path=f"{path}.{missing}", expected=expected[missing], actual="<missing>")
            )
        for extra in sorted(actual_keys - expected_keys):
            mismatches.append(
                ReplayMismatch(path=f"{path}.{extra}", expected="<missing>", actual=actual[extra])
            )
        for key in sorted(expected_keys & actual_keys):
            mismatches.extend(
                _collect_mismatches(expected[key], actual[key], path=f"{path}.{key}")
            )
        return mismatches

    if isinstance(expected, list):
        mismatches: list[ReplayMismatch] = []
        if len(expected) != len(actual):
            mismatches.append(
                ReplayMismatch(path=f"{path}.length", expected=len(expected), actual=len(actual))
            )
        limit = min(len(expected), len(actual))
        for idx in range(limit):
            mismatches.extend(
                _collect_mismatches(expected[idx], actual[idx], path=f"{path}[{idx}]")
            )
        return mismatches

    if expected != actual:
        return [ReplayMismatch(path=path, expected=expected, actual=actual)]
    return []


def compare_execution_graphs(
    expected_trace: ExecutionTrace,
    actual_trace: ExecutionTrace,
) -> ReplayVerdict:
    """Compare two traces with strict full-graph equality."""
    expected_graph = _canonical_trace(expected_trace)
    actual_graph = _canonical_trace(actual_trace)
    mismatches = _collect_mismatches(expected_graph, actual_graph)
    if mismatches:
        return ReplayVerdict(status="FAIL", mismatches=mismatches)
    return ReplayVerdict(status="PASS", mismatches=[])


def compare_structured_payloads(
    expected_payload: dict[str, Any],
    actual_payload: dict[str, Any],
) -> ReplayVerdict:
    """Compare arbitrary runtime artifacts using the same strict semantics."""
    mismatches = _collect_mismatches(expected_payload, actual_payload)
    if mismatches:
        return ReplayVerdict(status="FAIL", mismatches=mismatches)
    return ReplayVerdict(status="PASS", mismatches=[])
