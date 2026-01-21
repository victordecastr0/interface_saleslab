from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from db.engine import get_engine
from db.repos import vtal_repo
from ui.formatters import fmt_cnpj, fmt_date, fmt_monetary_value, fmt_rg, fmt_cpf
from ui.sections import address_helpers
from ui.sections.audit_helpers import create_decision_structure, update_audit_step_features
from ui.tables import build_tabela_dividas


def build_first_analysis_info_for_lead(lead, *, db_engine) -> None:
    st.subheader("Informações Básicas")

    with st.expander("Análise Cadastral"):
        build_on_register_analysis(lead, db_engine=db_engine)

    with st.expander("Análise Viabilidade - V.Tal"):
        address_helpers.build_availability_analysis(lead, db_engine=db_engine)

    with st.expander("Comprovação de Identidade"):
        build_identity_analysis(lead, db_engine=db_engine)

    with st.expander("Comprovação de Endereço"):
        address_helpers.build_address_analysis(lead, db_engine=db_engine)

    with st.expander("Análise Histórico - V.Tal"):
        build_vtal_analysis(lead, db_engine=db_engine)

    with st.expander("Análise Google Street View"):
        address_helpers.build_street_view_analysis(lead, db_engine=db_engine)

    st.divider()


def build_detailed_analysis_info_for_lead(lead, *, db_engine) -> None:
    st.subheader("Informações Adicionais")

    with st.expander("Análise Histórico Jurídico - Escavador"):
        build_escavador_analysis(lead, db_engine=db_engine)

    with st.expander("Análise Completa - Serasa"):
        build_serasa_analysis(lead, db_engine=db_engine)

    if lead.get("cnpj") is not None:
        with st.expander("Análise Cadastral - CNPJ"):
            build_cnpj_analysis(lead, db_engine=db_engine)


def build_on_register_analysis(lead, *, db_engine) -> None:
    infomais_analysis = lead["serasa_infomais"]

    register_data_columns = st.columns(3)
    with register_data_columns[0]:
        st.caption("Dia reservado para pagemento")

        if lead["payment_day"] is None or pd.isna(lead["payment_day"]):
            st.write("—")
        else:
            st.write(str(int(lead["payment_day"])))

    with register_data_columns[1]:
        st.caption("Método de pagamento")

        if lead["payment_method"] is None or pd.isna(lead["payment_method"]):
            st.write("—")
        else:
            st.write(lead["payment_method"].title())

    with register_data_columns[2]:
        st.caption("Data agendada para Instalação")
        st.write(fmt_date(lead["installation_date"]))

    serasa_cols = st.columns(3)
    with serasa_cols[0]:
        st.caption("Resultado preliminar Serasa - Infomais")

        if infomais_analysis is None:
            st.write("—")
        else:
            st.write(f"Risco **{infomais_analysis['riskTriage']['riskCode']}**")

    with serasa_cols[1]:
        st.caption("Data consulta Serasa - Infomais")
        st.write(fmt_date(lead["serasa_infomais_dt"]))

    with serasa_cols[2]:
        if infomais_analysis is not None:
            if "bolsaFamilia" in infomais_analysis:
                st.write(":red[**O lead participa de programas assistênciais do governo**]")
            else:
                st.write(":green[O lead **não** participa de programas assistênciais do governo]")

    st.write(" ")
    if infomais_analysis is not None:
        affinity = "não " if infomais_analysis["afinidadeBandaLarga"] == "false" else ""
        color = "red" if affinity == "não " else "green"

        lead_affinity_desc = f":{color}[**O lead {affinity}possui afinidade com o mercado de Telecom**]"
        st.write(lead_affinity_desc)

    create_decision_structure(
        "Resultado Análise Infomais",
        "informais",
        lead,
        db_engine=db_engine,
    )


def build_identity_analysis(lead, *, db_engine) -> None:
    identity_data_columns = st.columns(3)
    with identity_data_columns[0]:
        st.caption("CPF Cadastrado")
        st.write(fmt_cpf(lead["cpf"]))

    with identity_data_columns[1]:
        st.caption("RG Cadastrado")
        st.write(fmt_rg(lead["rg"]))

    with identity_data_columns[2]:
        st.caption("Plataforma para verificação do Score Biométrico")
        st.write("www.brflow.com.br")

    identity_data_columns_bottom = st.columns(2)

    with identity_data_columns_bottom[0]:
        st.caption("Link do documento enviado")
        doc_url = lead["doc_link"] if not pd.isna(lead["doc_link"]) else "—"
        st.write(doc_url)
    with identity_data_columns_bottom[1]:
        st.write(" ")
        if lead["stolen_documents"] == {}:
            st.write(":green[**Documentos pessoais não possuem histórico recente de furto**]")
        else:
            st.write(":red[**Documentos pessoais _POSSUEM_ histórico recente de furto**]")

    create_decision_structure(
        "Resultado Análise Documento Pessoal",
        "consumer_doc",
        lead,
        db_engine=db_engine,
    )
    create_decision_structure(
        "Resultado Análise ClearSale (Biometria + Liveliness)",
        "biometrics",
        lead,
        db_engine=db_engine,
    )


def build_cnpj_analysis(lead, *, db_engine) -> None:
    if lead["doc_situation"] is None:
        st.caption("CNPJ Cadastrado")
        st.write(lead["cnpj"])

        st.error("O CNPJ cadastrado é **INVÁLIDO**!")

        if lead["hzn_corp_doc_result"] != "reprovado":
            update_audit_step_features(
                db_engine=db_engine,
                lead_id=lead["lead_id"],
                decision="reprovado",
                field="corp_doc",
            )
        return

    cnpj_data_columns = st.columns(4)
    cnpj_result = lead["cnpj_json"]

    with cnpj_data_columns[0]:
        st.caption("CNPJ Consultado")
        st.write(fmt_cnpj(cnpj_result["cnpj"]))

    with cnpj_data_columns[1]:
        st.caption("Razão Social (R.F.)")
        st.write(cnpj_result["razao_social"])

    with cnpj_data_columns[2]:
        st.caption("Situação cadastral (R.F.)")
        st.write(cnpj_result["descricao_situacao_cadastral"])

    with cnpj_data_columns[3]:
        time_since_opening = (
            date.today()
            - datetime.strptime(cnpj_result["data_inicio_atividade"], "%Y-%m-%d").date()
        ).days
        age_message = ":green[**(≥ 90 dias)**]" if time_since_opening >= 90 else ":red[**(< 90 dias)**]"

        st.caption("Data de abertura (R.F.)")
        st.write(f"{fmt_date(cnpj_result['data_inicio_atividade'])} {age_message}")

    st.caption("Comprovante de situação cadastral CNPJ enviado")
    st.write(lead["doc_link_corporate"])

    if time_since_opening < 90 or cnpj_result["descricao_situacao_cadastral"] != "ATIVA":
        if lead["hzn_corp_doc_result"] != "reprovado":
            st.error(
                "CNPJ Reprovado (Situação cadastral inválida ou < 90 dias) - "
                f"{fmt_date(date.today())}"
            )
            update_audit_step_features(
                db_engine=db_engine,
                lead_id=lead["lead_id"],
                decision="reprovado",
                field="corp_doc",
            )
        else:
            st.error(
                "CNPJ Reprovado (Situação cadastral inválida ou < 90 dias) - "
                f"{fmt_date(lead['hzn_corp_doc_dt'])}"
            )
    else:
        create_decision_structure(
            "Resultado Análise Comprovante CNPJ",
            "corp_doc",
            lead,
            db_engine=db_engine,
        )


def build_vtal_analysis(lead, *, db_engine) -> None:
    if lead["vtal_address"] is None:
        st.warning("Endereço ainda não foi corretamente cadastrado...")
        return

    st.warning(
        "**Importante**: considerar que a análise apresentada leva em consideração "
        "todos os complementos existentes para o conjunto CEP + Número"
    )

    address = lead["vtal_address"]["address"]
    add_df = fetch_vtal_history(address)

    with st.expander("Histórico completo de HCs"):
        st.dataframe(add_df, hide_index=True)

    active_client = len(add_df[add_df["Status - V.Tal"] == "hc_ativo"])
    active_client = ":green[**Não**]" if active_client == 0 else ":red[**Sim**]"

    today = pd.to_datetime("today")
    max_date = today - pd.DateOffset(months=24)

    churn_vol_history = add_df[
        (add_df["Tipo Churn"] == "voluntario")
        & (pd.to_datetime(add_df["Data - Retirada"]) >= max_date)
    ]
    churn_vol_history["Mês Churn"] = churn_vol_history["Mês Churn"].str.replace("M", "").astype(int)

    with st.expander("Histórico de Churn VOL - Últimos 24 meses"):
        st.dataframe(churn_vol_history, hide_index=True)

    churn_vol_filter = (
        ":green[**Não**]"
        if len(churn_vol_history[churn_vol_history["Mês Churn"] <= 3]) == 0
        else ":red[**Sim**]"
    )

    churn_invol_history = add_df[
        (add_df["Tipo Churn"] == "involuntario")
        & (pd.to_datetime(add_df["Data - Retirada"]) >= max_date)
    ]
    churn_invol_history["Mês Churn"] = churn_invol_history["Mês Churn"].str.replace("M", "").astype(int)

    with st.expander("Histórico de Churn INVOL - Últimos 24 meses"):
        st.dataframe(churn_invol_history, hide_index=True)

    churn_invol_filter = (
        ":green[**Não**]"
        if len(churn_invol_history[churn_invol_history["Mês Churn"] <= 6]) == 0
        else ":red[**Sim**]"
    )

    vtal_data_columns = st.columns(3)
    with vtal_data_columns[0]:
        st.caption("Cliente V.Tal Ativo")
        st.write(active_client)

    with vtal_data_columns[1]:
        st.caption("Churn VOL em até 3 meses")
        st.write(churn_vol_filter)

    with vtal_data_columns[2]:
        st.caption("Churn INVOL em até 6 meses")
        st.write(churn_invol_filter)

    create_decision_structure(
        "Resultado Análise Cliente V.Tal",
        "vtal_client",
        lead,
        db_engine=db_engine,
    )
    create_decision_structure(
        "Resultado Análise HCs V.Tal",
        "vtal_qty_hc",
        lead,
        db_engine=db_engine,
    )


@st.cache_data(show_spinner=False)
def fetch_vtal_history(address: dict) -> pd.DataFrame:
    db_engine = get_engine("local")
    return vtal_repo.fetch_vtal_history(db_engine, address)


def build_escavador_analysis(lead, *, db_engine) -> None:
    escavador_data_columns = st.columns(2)

    n_processos_reu = lead["active_cases_as_defendant"] if not pd.isna(lead["active_cases_as_defendant"]) else 0
    n_processos_criminais = (
        len(lead["active_criminal_cases"]) if lead["active_criminal_cases"] is not None else 0
    )

    with escavador_data_columns[0]:
        st.caption("Processo Ativos (como Réu)")
        st.write(str(int(n_processos_reu)))

    with escavador_data_columns[1]:
        st.caption("Processos Criminais Ativos (como Réu)")
        st.write(str(n_processos_criminais))

    if n_processos_criminais == 0:
        if n_processos_reu <= 4:
            if lead["hzn_court_case_result"] != "aprovado":
                st.success(
                    "Cliente **aprovado** na análise jurídica (< 5 _Processos Ativos_ como réu) - "
                    f"{fmt_date(date.today())}"
                )
                update_audit_step_features(
                    db_engine=db_engine,
                    lead_id=lead["lead_id"],
                    decision="aprovado",
                    field="court_case",
                )
            else:
                st.success(
                    "Cliente **aprovado** na análise jurídica (< 5 _Processos Ativos_ como réu) - "
                    f"{fmt_date(lead['hzn_court_case_dt'])}"
                )
        else:
            create_decision_structure(
                "Resultado Análise Escavador",
                "court_case",
                lead,
                db_engine=db_engine,
            )
            st.warning("A instalação deste cliente está sujeita à taxa de R$ 199,00.")
    else:
        if lead["hzn_court_case_result"] != "reprovado":
            st.error(
                "Cliente **reprovado** na análise jurídica (> 1 _Processo Criminal_ ativo) - "
                f"{fmt_date(date.today())}"
            )
            update_audit_step_features(
                db_engine=db_engine,
                lead_id=lead["lead_id"],
                decision="reprovado",
                field="court_case",
            )
        else:
            st.error(
                "Cliente **reprovado** na análise jurídica (> 1 _Processo Criminal_ ativo) - "
                f"{fmt_date(lead['hzn_court_case_dt'])}"
            )


def build_serasa_analysis(lead, *, db_engine) -> None:
    if lead["statusregistration"] is None:
        st.error("O CPF cadastrado é inválido")
        return

    dividas = lead["serasa_json"]["negativeData"]["pefin"]

    valor_total = dividas["summary"]["balance"]
    desc_dividas = dividas["pefinResponse"]

    score_serasa = int(lead["credit_score"]) if not pd.isna(lead["credit_score"]) else "—"

    serasa_data_columnns = st.columns(4)
    with serasa_data_columnns[0]:
        st.caption("Status CPF")
        st.write(lead["statusregistration"])

    with serasa_data_columnns[1]:
        st.caption("Score SERASA")
        st.write(str(score_serasa))

    with serasa_data_columnns[2]:
        st.caption("Dívidas Comerciais")
        st.write(fmt_monetary_value(valor_total))

    with serasa_data_columnns[3]:
        st.caption("Renda estimada")
        st.write(fmt_monetary_value(lead["renda_estimada"]))

    if dividas["summary"]["count"] > 0:
        st.write("**Histórico de dívidas**")

        tabela_dividas = build_tabela_dividas(desc_dividas)
        st.dataframe(
            tabela_dividas,
            hide_index=True,
            column_config={
                "Valor da dívida (R$)": st.column_config.NumberColumn(format="localized"),
                "Ocorrência da dívida": st.column_config.DateColumn(format="localized"),
            },
        )

    if lead["statusregistration"] != "REGULAR":
        st.write(":red[**Status do CPF reprovado (não _Regular_)**]")

        if lead["hzn_serpro_result"] != "reprovado":
            update_audit_step_features(
                db_engine=db_engine,
                lead_id=lead["lead_id"],
                decision="reprovado",
                field="serpro",
            )
    else:
        st.write(" ")
        st.write(":green[Status do CPF **aprovado** (_Regular_)]")

        if lead["hzn_serpro_result"] != "aprovado":
            update_audit_step_features(
                db_engine=db_engine,
                lead_id=lead["lead_id"],
                decision="aprovado",
                field="serpro",
            )

        if valor_total > 100:
            if lead["hzn_serasa_result"] != "reprovado":
                st.error(
                    "Cliente **reprovado** na análise Serasa (dívida > R$ 100,00) - "
                    f"{fmt_date(date.today())}"
                )
                update_audit_step_features(
                    db_engine=db_engine,
                    lead_id=lead["lead_id"],
                    decision="reprovado",
                    field="serasa",
                )
            else:
                st.error(
                    "Cliente **reprovado** na análise Serasa (dívida > R$ 100,00) - "
                    f"{fmt_date(lead['hzn_serasa_dt'])}"
                )
        else:
            if score_serasa != "—" and score_serasa >= 450:
                if lead["hzn_serasa_result"] != "aprovado":
                    st.success(
                        "Cliente **aprovado** na análise Serasa - "
                        f"{fmt_date(date.today())}"
                    )
                    update_audit_step_features(
                        db_engine=db_engine,
                        lead_id=lead["lead_id"],
                        decision="aprovado",
                        field="serasa",
                    )
                else:
                    st.success(
                        "Cliente **aprovado** na análise Serasa - "
                        f"{fmt_date(lead['hzn_serasa_dt'])}"
                    )

            else:
                create_decision_structure(
                    "Resultado Análise Serasa",
                    "serasa",
                    lead,
                    db_engine=db_engine,
                )
                st.warning("A instalação deste cliente está sujeita à taxa de R$ 199,00.")
