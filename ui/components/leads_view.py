from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
import streamlit as st


def _normalize_digits(value: str) -> str:
    return "".join(char for char in str(value) if char.isdigit())


def _apply_leads_filter(df: pd.DataFrame, filter_type: str, filter_value: str) -> pd.DataFrame:
    if filter_type == "Nenhum":
        return df

    cleaned_value = str(filter_value or "").strip().lower()
    if not cleaned_value:
        return df

    if filter_type == "Nome":
        if "name" not in df.columns:
            st.warning("Filtro por nome indisponível (coluna ausente).")
            return df
        return df[df["name"].astype(str).str.lower().str.contains(cleaned_value, case=False, na=False)]

    if filter_type == "CPF":
        if "cpf" not in df.columns:
            st.warning("Filtro por CPF indisponível (coluna ausente).")
            return df
        digits = _normalize_digits(cleaned_value)
        if not digits:
            return df
        cpf_series = df["cpf"].astype(str).str.replace(r"\D", "", regex=True)
        return df[cpf_series.str.contains(digits, na=False)]

    if filter_type == "CEP":        
        digits = _normalize_digits(cleaned_value)
        
        if not digits:
            return df
        
        cep_series = df["vtal_address"].apply(
            lambda x: x['address']['zipCode'] \
            if (x is not None) and ('address' in x) else ""
        )
        cep_series = cep_series.astype(str).str.replace(r"\D", "", regex=True)
        

        return df[cep_series.str.contains(digits, na=False)]

    return df


def status_badge(text: str) -> str:
    cls = {
        "Aprovado": "aprovado",
        "Aprovado - Auditoria": "aprovado",
        "Reprovado - Auditoria": "reprovado",
        "Reprovado - AddSales": "reprovado",
        "Em Negociação - AddSales": "pendente",
        "Pendente - Auditoria": "pendente",
        "Necessária auditoria": "auditavel",
    }.get(text, "default")
    return f'<span class="badge {cls}">{text}</span>'


def render_lead_card(row: pd.Series, selected: bool) -> None:
    rid = row["lead_id"]
    nome = str(row["name"]).strip().title()
    stat = str(row["status"])
    when = str(row["lead_dt"])

    with st.container(border=True):
        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            prefix = "🔘 " if selected else ""
            st.markdown(f"**{prefix}{nome}**")
            st.caption(f"ID: `{rid}` • Criado em: {when}")

        with c2:
            st.markdown(status_badge(stat), unsafe_allow_html=True)
            if selected:
                st.button(
                    "Selecionado ✓",
                    key=f"sel_{rid}",
                    disabled=True,
                    use_container_width=True,
                )
            else:
                if st.button("Ver detalhes", key=f"sel_{rid}", use_container_width=True):
                    st.session_state["selected_lead_id"] = rid
                    st.rerun()


def manage_lead_selection_visuals(df: pd.DataFrame) -> None:
    selected_id = st.session_state.get("selected_lead_id")
    for _, row in df.iterrows():
        is_selected = str(row["lead_id"]) == str(selected_id)
        render_lead_card(row, is_selected)


def build_lead_overall_display(df: pd.DataFrame, *, items_per_page: int) -> None:
    st.subheader("Leads por Status")

    prev_filter_type = st.session_state.get("leads_filter_type", "Nenhum")
    prev_filter_value = st.session_state.get("leads_filter_value", "")

    filter_left, filter_right = st.columns([1, 2])
    with filter_left:
        selected_filter_type = st.selectbox(
            "Filtrar por",
            ["Nenhum", "CEP", "CPF", "Nome"],
            key="leads_filter_type_select",
        )
    with filter_right:
        filter_placeholder = {
            "CEP": "Digite o CEP",
            "CPF": "Digite o CPF",
            "Nome": "Digite o nome",
            "Nenhum": "Selecione um tipo de filtro",
        }[selected_filter_type]
        selected_filter_value = st.text_input(
            "Valor do filtro",
            key="leads_filter_value_input",
            placeholder=filter_placeholder,
            disabled=selected_filter_type == "Nenhum",
        )

    all_statuses = sorted(df["status"].dropna().unique().tolist())
    status_options = ["Todos"] + all_statuses

    prev_selected = st.session_state.get("leads_selected_status", "Todos")
    selected_status = st.selectbox(
        "Filtrar status",
        status_options,
        index=0,
        key="leads_status_select",
    )

    if selected_status != prev_selected:
        st.session_state["leads_selected_status"] = selected_status
        st.session_state["leads_page"] = 1

    if (
        selected_filter_type != prev_filter_type
        or selected_filter_value != prev_filter_value
    ):
        st.session_state["leads_filter_type"] = selected_filter_type
        st.session_state["leads_filter_value"] = selected_filter_value
        st.session_state["leads_page"] = 1

    if selected_status == "Todos":
        df_filtered = df.copy()
    else:
        df_filtered = df[df["status"] == selected_status].copy()

    df_filtered = _apply_leads_filter(
        df_filtered,
        st.session_state.get("leads_filter_type", "Nenhum"),
        st.session_state.get("leads_filter_value", ""),
    )

    total_items = len(df_filtered)
    total_pages = max((total_items - 1) // items_per_page + 1, 1)

    st.session_state.setdefault("leads_page", 1)
    st.session_state["leads_page"] = min(max(1, st.session_state["leads_page"]), total_pages)

    top_left, top_mid, top_right = st.columns([1, 2, 1])
    with top_left:
        prev_btn = st.button(
            "◀️ Anterior",
            use_container_width=True,
            disabled=st.session_state["leads_page"] <= 1,
        )
    with top_mid:
        st.write(
            f"Página {st.session_state['leads_page']} de {total_pages} — {total_items} itens"
        )
    with top_right:
        next_btn = st.button(
            "Próxima ▶️",
            use_container_width=True,
            disabled=st.session_state["leads_page"] >= total_pages,
        )

    if prev_btn and st.session_state["leads_page"] > 1:
        st.session_state["leads_page"] -= 1
        st.rerun()
    if next_btn and st.session_state["leads_page"] < total_pages:
        st.session_state["leads_page"] += 1
        st.rerun()

    start = (st.session_state["leads_page"] - 1) * items_per_page
    end = start + items_per_page
    page_df = df_filtered.iloc[start:end]

    manage_lead_selection_visuals(page_df)

    b_left, b_mid, b_right = st.columns([1, 2, 1])
    with b_left:
        prev_btn2 = st.button(
            "◀️ Anterior",
            key="prev_bottom",
            use_container_width=True,
            disabled=st.session_state["leads_page"] <= 1,
        )
    with b_mid:
        goto = st.number_input(
            "Ir para página",
            min_value=1,
            max_value=total_pages,
            value=st.session_state["leads_page"],
            step=1,
            label_visibility="collapsed",
        )
        if goto != st.session_state["leads_page"]:
            st.session_state["leads_page"] = int(goto)
            st.rerun()
    with b_right:
        next_btn2 = st.button(
            "Próxima ▶️",
            key="next_bottom",
            use_container_width=True,
            disabled=st.session_state["leads_page"] >= total_pages,
        )

    if prev_btn2 and st.session_state["leads_page"] > 1:
        st.session_state["leads_page"] -= 1
        st.rerun()
    if next_btn2 and st.session_state["leads_page"] < total_pages:
        st.session_state["leads_page"] += 1
        st.rerun()


def build_detailed_lead_display(
    df: pd.DataFrame,
    *,
    render_general: Callable[[dict], None],
    render_first_analysis: Callable[[dict], None],
    render_detailed_analysis: Callable[[dict], None],
    render_audit: Optional[Callable[[dict], None]] = None,
) -> None:
    selected_id = st.session_state.get("selected_lead_id")

    with st.container(border=True):
        st.header("Dados do Lead")

        if not selected_id:
            st.info("Selecione um lead na lista ao lado para ver os detalhes.")
            return

        lead_data = df.loc[df["lead_id"] == selected_id].iloc[0].to_dict()

        render_general(lead_data)
        render_first_analysis(lead_data)
        render_detailed_analysis(lead_data)

        if render_audit and lead_data.get("hzn_audit"):
            st.divider()
            render_audit(lead_data)
