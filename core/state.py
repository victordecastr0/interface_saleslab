from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

import streamlit as st


@dataclass(frozen=True)
class LeadsQuery:
    start: date
    end: date
    version: int


def init_session_state() -> None:
    """
    Centralized session_state defaults.
    Keep these minimal; expand as you touch features.
    """
    st.session_state.setdefault("leads_page", 1)
    st.session_state.setdefault("leads_selected_status", "Todos")
    st.session_state.setdefault("leads_selected_lead_id", None)
    st.session_state.setdefault("leads_filter_type", "Nenhum")
    st.session_state.setdefault("leads_filter_value", "")
    st.session_state.setdefault("leads_data_version", 0)
    st.session_state.setdefault("_leads_query", None)
    st.session_state.setdefault("df_leads", None)


def bump_leads_version() -> None:
    """
    Invalidate the current leads snapshot.
    """
    st.session_state["leads_data_version"] = (
        int(st.session_state.get("leads_data_version", 0)) + 1
    )
    st.session_state["_leads_query"] = None


def get_leads_query(start: date, end: date) -> LeadsQuery:
    return LeadsQuery(
        start=start,
        end=end,
        version=int(st.session_state.get("leads_data_version", 0)),
    )
