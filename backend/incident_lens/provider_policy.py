"""Explicit provider failure and replay-choice semantics."""

from dataclasses import dataclass
from typing import Literal, Optional


ProviderChoice = Literal["retry", "replay"]
Execution = Literal["new_analysis", "stored_result"]


@dataclass(frozen=True)
class ProviderDecision:
    outcome: Literal["provider_succeeded", "provider_failed", "replay_selected"]
    execution: Execution
    provider_error: Optional[str] = None
    prior_run_id: Optional[str] = None


def resolve_provider_outcome(
    *,
    provider_succeeded: bool,
    choice: ProviderChoice = "retry",
    replay_run_id: Optional[str] = None,
    provider_error: Optional[str] = None,
) -> ProviderDecision:
    """Never silently substitute a replay when a fresh provider call fails."""

    if choice not in {"retry", "replay"}:
        raise ValueError("choice must be retry or replay")
    if provider_succeeded:
        return ProviderDecision("provider_succeeded", "new_analysis")
    if choice == "replay" and replay_run_id:
        return ProviderDecision("replay_selected", "stored_result", provider_error, replay_run_id)
    return ProviderDecision("provider_failed", "new_analysis", provider_error)
