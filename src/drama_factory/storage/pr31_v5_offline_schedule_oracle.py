"""PR-31c3c: PURE schedule oracle for the future TxLab v5 dual-Runner plan.

No DB, networking, credentials, source data, timeouts, or model requests.
Predicts a sequential *reference specification* only. Actual local SDK
histories are verified separately; matching a model is not remote Turso
linearizability or cross-Runner proof.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

OPS = (
    "intent_a", "intent_b", "task_a", "task_b", "pause", "resume",
)


class OfflineScheduleDenied(ValueError):
    """Fixed-message validation, no operator or business inputs."""


@dataclass(frozen=True)
class ReferenceState:
    """Only symbolic Worker roles and discrete gate epochs; no customer data."""

    epoch: int = 1
    gate: str = "running"
    intent_owner: str | None = None
    submitted_roles: tuple[str, ...] = ()
    pause_events: int = 0
    resume_events: int = 0

    def step(self, operation: str) -> tuple["ReferenceState", bool]:
        """Compute the expected outcome of one ordered, atomic operation.

        The two synthetic Workers share a 0.60 daily limit and each requests
        0.40. Both were claimed under original epoch=1 and cannot acquire
        newer rights by reusing an old token. All active business operations
        must first pass the same durable gate.
        """
        if operation not in OPS:
            raise OfflineScheduleDenied("Unknown symbolic action")
        if operation == "pause":
            return (
                (replace(
                    self, gate="paused", epoch=self.epoch + 1,
                    pause_events=self.pause_events + 1,
                ), True)
                if self.gate == "running" else (self, False)
            )
        if operation == "resume":
            return (
                (replace(
                    self, gate="running", epoch=self.epoch + 1,
                    resume_events=self.resume_events + 1,
                ), True)
                if self.gate == "paused" else (self, False)
            )
        if self.gate != "running" or self.epoch != 1:
            return self, False
        role = operation[-1]
        if operation.startswith("intent_"):
            # Two 0.40 holds cannot fit under the shared 0.60 cap.
            if self.intent_owner is not None:
                return self, False
            return replace(self, intent_owner=role), True
        if self.intent_owner != role or role in self.submitted_roles:
            return self, False
        return replace(
            self, submitted_roles=self.submitted_roles + (role,),
        ), True


def predict_offline_schedule(operations: tuple[str, ...]) -> dict:
    """Return a complete sanitized outcome for a finite symbolic ordering.

    Only declared symbols are accepted. Retain no execution trace containing
    IDs, task IDs, amounts, paths, or exception messages.
    """
    if not isinstance(operations, tuple) or not operations:
        raise OfflineScheduleDenied("Finite fixed schedule required")
    if len(operations) > len(OPS) or len(set(operations)) != len(operations):
        raise OfflineScheduleDenied("Only unique symbolic operations allowed")
    if any(type(op) is not str or op not in OPS for op in operations):
        raise OfflineScheduleDenied("Unknown symbolic operation")
    current = ReferenceState()
    outcomes: list[bool] = []
    for op in operations:
        current, accepted = current.step(op)
        outcomes.append(accepted)
    return {
        "accepted": tuple(outcomes),
        "epoch": current.epoch,
        "gate": current.gate,
        "intents": int(current.intent_owner is not None),
        "tasks": len(current.submitted_roles),
        "held_budget_reservations": int(current.intent_owner is not None),
        "pause_events": current.pause_events,
        "resume_events": current.resume_events,
        "offline_sequential_oracle_only": True,
        "remote_multi_runner_verified": False,
        "remote_txlab_write_calls": 0,
        "paid_provider_calls": 0,
        "may_resume_production": False,
        "live_cutover_permitted": False,
    }
