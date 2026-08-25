from __future__ import annotations

from dataclasses import dataclass

from atlas_knowledge import AGENT_LOOP_POLICY


@dataclass(frozen=True)
class AgentLoopConfig:
    max_recovery_attempts: int = 3
    require_verification: bool = True
    learn_from_verified_results: bool = True


DEFAULT_AGENT_LOOP = AgentLoopConfig()


def agent_runtime_prompt() -> str:
    """Runtime instructions for goal-oriented autonomous execution."""
    return AGENT_LOOP_POLICY


def should_stop_after_failure(attempts: int, config: AgentLoopConfig = DEFAULT_AGENT_LOOP) -> bool:
    """Prevent autonomous recovery from turning into an infinite retry loop."""
    return attempts >= config.max_recovery_attempts


def learning_kind(success: bool, verified: bool) -> str | None:
    """Only verified outcomes are eligible for durable procedural learning."""
    if not verified:
        return None
    return "skill" if success else "lesson"
