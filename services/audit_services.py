from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.engine import Engine

from db.repos import lead_repo


@dataclass(frozen=True)
class AuditResult:
    ok: bool
    message: str = ""


def set_audit_step_decision(
    engine: Engine,
    *,
    lead_id: str,
    field_suffix: str,
    decision: str,
    valid_suffixes: set[str],
) -> AuditResult:
    """
    Service-layer validation + persistence for a single audit step.
    """
    if not lead_id:
        return AuditResult(False, "lead_id vazio")

    if field_suffix not in valid_suffixes:
        return AuditResult(False, f"suffix inválido: {field_suffix!r}")

    if decision not in {"Aprovado", "Pendente", "Reprovado"}:
        return AuditResult(False, f"decisão inválida: {decision!r}")

    lead_repo.update_audit_step(
        engine,
        lead_id=lead_id,
        field_suffix=field_suffix,
        decision=decision,
    )
    return AuditResult(True)


def set_final_audit_result(
    engine: Engine,
    *,
    lead_id: str,
    decision: str,
    pending_obs: Optional[str] = None,
    denied_obs: Optional[str] = None,
) -> AuditResult:
    """
    Final audit decision with notes.
    Keeps rule checks here (UI just passes inputs).
    """
    if not lead_id:
        return AuditResult(False, "lead_id vazio")

    if decision not in {"Aprovado", "Pendente", "Reprovado"}:
        return AuditResult(False, f"decisão inválida: {decision!r}")

    # Optional light normalization (no behavior change)
    pending_obs = (pending_obs or "").strip() or None
    denied_obs = (denied_obs or "").strip() or None

    # Optional consistency: only allow note in its matching state
    # (Keep permissive to avoid breaking flows; can harden later.)
    lead_repo.update_audit_result(
        engine,
        lead_id=lead_id,
        decision=decision,
        pending_obs=pending_obs,
        denied_obs=denied_obs,
    )
    return AuditResult(True)