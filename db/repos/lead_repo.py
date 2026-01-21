from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def fetch_leads(engine: Engine, d_start: date, d_end: date) -> pd.DataFrame:
    """
    Fetch leads in a date range.
    """
    query = text(
        """
        SELECT
            l.*,
            sar.statusregistration,
            sar.credit_score,
            sar.all_addresses,
            sar.all_phones,
            sar.stolen_documents,
            sar.renda_estimada,
            sar.raw_json AS serasa_json,
            ear.active_cases_as_defendant,
            ear.active_criminal_cases,
            csar.doc_situation,
            csar.activity_start_date,
            csar.raw_json AS cnpj_json
        FROM "lead" l
            LEFT JOIN serasa_api_results sar ON l.cpf = sar.documentnumber
            LEFT JOIN escavador_api_results ear ON l.cpf = ear.cpf_cnpj
            LEFT JOIN company_situation_api_results csar ON l.cnpj = csar.document
        WHERE lead_dt BETWEEN :d_start AND :d_end;
        """
    )

    with engine.begin() as conn:
        return pd.read_sql(query, conn, params={"d_start": d_start, "d_end": d_end})


def update_audit_step(
    engine: Engine,
    lead_id: str,
    field_suffix: str,
    decision: str,
) -> None:
    """
    Update one audit step (hzn_{suffix}_result + hzn_{suffix}_dt).
    field_suffix MUST be validated by caller (allowlist).
    """
    q = text(
        f"""
        UPDATE lead
        SET hzn_{field_suffix}_result = :decision,
            hzn_{field_suffix}_dt = NOW()
        WHERE lead_id = :lead_id;
        """
    )
    with engine.begin() as conn:
        conn.execute(q, {"decision": decision, "lead_id": lead_id})


def update_audit_result(
    engine: Engine,
    lead_id: str,
    decision: str,
    pending_obs: Optional[str] = None,
    denied_obs: Optional[str] = None,
) -> None:
    """
    Update final audit result and notes.
    """
    q = text(
        """
        UPDATE lead
        SET hzn_final_result = :decision,
            hzn_final_result_dt = NOW(),
            hzn_pending = :pending_obs,
            hzn_denied = :denied_obs
        WHERE lead_id = :lead_id;
        """
    )
    with engine.begin() as conn:
        conn.execute(
            q,
            {
                "decision": decision,
                "pending_obs": pending_obs,
                "denied_obs": denied_obs,
                "lead_id": lead_id,
            },
        )