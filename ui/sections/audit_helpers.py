from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from core.state import bump_leads_version
from db.repos import lead_repo
from services import audit_services


AUDIT_SUFFIXES = {
    "address_info",
    "biometrics",
    "consumer_doc",
    "corp_doc",
    "court_case",
    "informais",
    "serasa",
    "serpro",
    "vtal_client",
    "vtal_qty_hc",
    "street_view",
}


def validate_audit_suffix(value: str, valid_suffixes: Iterable[str] = AUDIT_SUFFIXES) -> str:
    if value not in valid_suffixes:
        raise ValueError(f"Invalid audit suffix/field: {value!r}")
    return value


def create_decision_structure(
    title: str,
    suffix: str,
    lead: dict,
    *,
    db_engine,
) -> None:
    suffix = validate_audit_suffix(str(suffix))
    current_status = lead.get(f"hzn_{suffix}_result")
    lead_id = lead["lead_id"]

    if pd.isna(current_status) or current_status == "pendente":
        index = 0
    elif current_status == "aprovado":
        index = 1
    else:
        index = 2

    col_desc, col_input, col_save = st.columns([0.8, 1.6, 1])

    with col_desc:
        st.write(f"**{title}:**")
    with col_input:
        sel = st.radio(
            "",
            ["Análise Pendente", "Aprovado", "Reprovado"],
            index=index,
            horizontal=True,
            label_visibility="collapsed",
            key=f"radio_{suffix}",
        )
    with col_save:
        if st.button("Salvar", use_container_width=True, key=f"save_{suffix}"):
            analysis_result_map = {
                "Análise Pendente": "pendente",
                "Aprovado": "aprovado",
                "Reprovado": "reprovado",
            }

            analysis_result = analysis_result_map.get(sel, "pendente")
            lead_repo.update_audit_step(db_engine, lead_id, suffix, analysis_result)

            bump_leads_version()
            st.rerun()


def update_audit_step_features(
    *,
    db_engine,
    lead_id: str,
    decision: str,
    field: str,
) -> None:
    field = validate_audit_suffix(str(field))
    result = audit_services.set_audit_step_decision(
        db_engine,
        lead_id=lead_id,
        field_suffix=field,
        decision=decision,
        valid_suffixes=AUDIT_SUFFIXES,
    )

    if not result.ok:
        st.error(result.message)
        return

    bump_leads_version()
    st.rerun()
