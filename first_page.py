import locale
import os
from datetime import date, datetime, timedelta
from functools import partial

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from auth import auth_gate
from clients import addsales_client
from core.state import bump_leads_version, get_leads_query, init_session_state
from db.engine import get_engine
from db.repos import lead_repo
from services import audit_services
from services.lead_status_service import define_lead_status
from ui.components.leads_view import build_detailed_lead_display, build_lead_overall_display
from ui.formatters import fmt_date, fmt_leads_features
from ui.sections.analysis import (
    build_detailed_analysis_info_for_lead,
    build_first_analysis_info_for_lead,
)
from ui.sections.general import build_general_info_for_lead
from ui.styles import inject_badges_css


locale.setlocale(locale.LC_ALL, "")


load_dotenv()
inject_badges_css()
init_session_state()

ITEMS_PER_PAGE = 10


@st.cache_data(show_spinner="Carregando leads...")
def load_leads_snapshot(d_start: date, d_end: date, version: int) -> pd.DataFrame:
    db_engine = get_engine("local")
    df = lead_repo.fetch_leads(db_engine, d_start=d_start, d_end=d_end)
    df = fmt_leads_features(df)

    if len(df) > 0:
        df["status"] = df.apply(define_lead_status, axis=1)
        df = df.sort_values("lead_dt", ascending=False)

    return df


def get_leads_dataframe(start: date, end: date) -> pd.DataFrame:
    leads_query = get_leads_query(start, end)
    if st.session_state.get("_leads_query") != leads_query:
        st.session_state["_leads_query"] = leads_query
        st.session_state["df_leads"] = load_leads_snapshot(
            leads_query.start, leads_query.end, leads_query.version
        )

    return st.session_state.get("df_leads") or pd.DataFrame()


def build_overall_metrics(df: pd.DataFrame, end_date) -> None:
    df_local = df.copy() if df is not None else pd.DataFrame()

    if "lead_dt" in df_local.columns:
        df_local["lead_dt"] = pd.to_datetime(df_local["lead_dt"], errors="coerce")

    end_ts = pd.to_datetime(end_date)
    week_start = end_ts - pd.Timedelta(days=7)

    total_leads = int(df_local.shape[0])
    status_col = (
        df_local["status"].fillna("")
        if "status" in df_local.columns
        else pd.Series([], dtype=str)
    )

    if "lead_dt" in df_local.columns:
        novos_leads = int(df_local[df_local["lead_dt"] >= week_start].shape[0])
    else:
        novos_leads = 0


    leads_aprovados = int(status_col.str.contains("Aprovado").sum()) if len(status_col) else 0
    leads_reprovados = int(status_col.str.contains("Reprovado").sum()) if len(status_col) else 0
    leads_abertos = int((status_col == "Aberto").sum()) if len(status_col) else 0

    if {"hzn_audit", "hzn_final_result"}.issubset(df_local.columns):
        leads_auditaveis = int(
            df_local[(df_local["hzn_audit"]) & (pd.isna(df_local["hzn_final_result"]))].shape[0]
        )
    else:
        leads_auditaveis = 0

    delta_novos_leads = 100 * (novos_leads / total_leads) if total_leads > 0 else 0
    delta_novos_leads = (
        f"{'+' if delta_novos_leads > 0 else ('-' if delta_novos_leads < 0 else '')}"
        f"{delta_novos_leads:.1f}%"
    )
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("Total de Leads no Período", f"{total_leads:,}".replace(",", "."))
    with k2:
        st.metric(
            "Leads da Última Semana",
            f"{novos_leads:,}".replace(",", "."),
            delta_novos_leads,
        )
    with k3:
        st.metric("Leads Aprovados", f"{leads_aprovados:,}".replace(",", "."))
    with k4:
        st.metric("Leads Reprovados", f"{leads_reprovados:,}".replace(",", "."))
    with k5:
        st.metric("**Leads Abertos**", f"{leads_abertos:,}".replace(",", "."))
    with k6:
        st.metric("**Leads Auditáveis**", f"{leads_auditaveis:,}".replace(",", "."))


def build_audit_structure(lead):
    st.subheader("Decisão da Auditoria")

    decision_made = not pd.isna(lead["hzn_final_result"])
    edit_mode = st.session_state.get("new_decision", False)

    controls_disabled = decision_made and not edit_mode
    
    st.session_state.setdefault("audit_action", None)

    audit_options_columns = st.columns(3)
    with audit_options_columns[0]:
        approve = st.button("✅ Aprovar", use_container_width=True, disabled=controls_disabled)

    with audit_options_columns[1]:
        pendency_click = st.button("⚠️ Pendência", use_container_width=True, disabled=controls_disabled)
    
    with audit_options_columns[2]:
        reject_click = st.button("🛑 Reprovar", use_container_width=True, disabled=controls_disabled)

    if pendency_click:
        st.session_state.audit_action = "pendente"
        st.session_state.new_decision = True
        st.rerun()
    if reject_click:
        st.session_state.audit_action = "reprovado"
        st.session_state.new_decision = True
        st.rerun()

    def submit_audit_result(decision: str, *, pending_obs: str | None, denied_obs: str | None) -> bool:
        addsales_token = os.getenv("ADDSALES_TOKEN")
        if not addsales_token:
            st.error("Token AddSales não encontrado.")
            return False

        payload = {
            "codigo_lead_addsales": lead["addsales_code"],
            "cpf": lead["cpf"],
            "data_auditoria": datetime.now().isoformat(),
            "descricao_pendencias": pending_obs,
            "motivos_reprovacao": denied_obs,
            "resultado_auditoria": decision,
        }

        try:
            addsales_client.update_lead(
                token=addsales_token,
                addsales_code=str(lead["addsales_code"]),
                payload=payload,
            )
        except Exception as exc:
            st.error(f"Erro AddSales: {exc}")
            return False

        update_audit_result_features(
            lead["lead_id"],
            decision,
            pending_obs=pending_obs,
            denied_obs=denied_obs,
        )
        return True

    if not decision_made or edit_mode:
        if approve:
            if submit_audit_result("aprovado", pending_obs=None, denied_obs=None):
                st.session_state.new_decision = False
                st.session_state.audit_action = None

        elif st.session_state.audit_action in ("pendente", "reprovado"):
            note = st.text_area(
                "Observação (obrigatória para registrar a decisão)",
                placeholder="Descreva o motivo…",
                height=110,
            )

            if st.button("Enviar análise", use_container_width=True):
                if not note.strip():
                    st.error("A observação é obrigatória para a decisão tomada")
                else:
                    final_decision = st.session_state.audit_action
                    observations = (
                        (None, note) if final_decision == "reprovado" else (note, None)
                    )
                    if submit_audit_result(
                        final_decision,
                        pending_obs=observations[0],
                        denied_obs=observations[1],
                    ):
                        st.session_state.new_decision = False
                        st.session_state.audit_action = None
    
    if decision_made:
        fmt_status = lead["status"].split(" - ")[0]
        color = (
            "red"
            if fmt_status == "Reprovado"
            else ("yellow" if fmt_status == "Pendente" else "green")
        )

        st.info(
            "Lead já auditado. Decisão feita: "
            f":{color}[**{fmt_status}**] - :{color}[**{fmt_date(lead['hzn_final_result_dt'])}**]"
        )

        if not edit_mode:
            if lead["hzn_final_result"] == "pendente":
                st.info(f"Motivos registrados: {lead['hzn_pending']}")
            elif lead["hzn_final_result"] == "reprovado":
                st.info(f"Motivos registrados: {lead['hzn_denied']}")

            if st.button("Editar decisão", use_container_width=True):
                st.session_state.new_decision = True
                st.rerun()
        else:
            if st.button("**Cancelar edição**", use_container_width=True, type="primary"):
                st.session_state.new_decision = False
                st.rerun()


def update_audit_result_features(lead_id, decision, pending_obs=None, denied_obs=None):
    result = audit_services.set_final_audit_result(
        db_engine,
        lead_id=lead_id,
        decision=decision,
        pending_obs=pending_obs,
        denied_obs=denied_obs,
    )

    if not result.ok:
        st.error(result.message)
        return

    bump_leads_version()
    st.rerun()


st.set_page_config(page_title="SalesLab", page_icon="🔬", layout="wide")
authenticator = auth_gate()

if st.session_state.get("authentication_status"):
    st.title("Histórico de Leads - SalesLab")

    with st.sidebar:
        name = st.session_state.name

        st.markdown(f"**Olá, {name}** 👋")
        authenticator.logout("Sair", "sidebar")


    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.subheader("Resumo de Leads")
    with c2:
        start = st.date_input(
            "Início",
            date.today() - timedelta(days=30),
            format="DD/MM/YYYY",
        )
    with c3:
        end = st.date_input("Fim", date.today(), format="DD/MM/YYYY")

    db_engine = get_engine("local")
    df_leads = get_leads_dataframe(start, end)

    if len(df_leads) == 0:
        st.error("No intervalo escolhido não existe nenhum lead...")
    else:
        build_overall_metrics(df_leads, end)

        if st.button(
            "**Atualizar Leads**",
            use_container_width=True,
            icon="🔄",
            type="tertiary",
        ):
            bump_leads_version()
            st.cache_data.clear()
            st.rerun()

        st.divider()

        left_pannel, right_pannel = st.columns([1, 1.8])
        with left_pannel:
            build_lead_overall_display(df_leads, items_per_page=ITEMS_PER_PAGE)
        with right_pannel:
            build_detailed_lead_display(
                df_leads,
                render_general=build_general_info_for_lead,
                render_first_analysis=partial(
                    build_first_analysis_info_for_lead,
                    db_engine=db_engine,
                ),
                render_detailed_analysis=partial(
                    build_detailed_analysis_info_for_lead,
                    db_engine=db_engine,
                ),
                render_audit=build_audit_structure,
            )

else:
    st.write(st.session_state.get("authentication_status"))
