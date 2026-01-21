import locale
locale.setlocale(locale.LC_ALL, '')

import ast
import os
import re
import json
import requests

import pandas as pd
import streamlit as st
import numpy as np

from ui.styles import inject_badges_css
from ui.tables import build_tabela_enderecos, build_tabela_telefones, build_tabela_dividas
from ui.formatters import (
    fmt_date, fmt_monetary_value, fmt_cpf, fmt_cnpj,
    fmt_rg, fmt_zipcode, fmt_leads_features,
)

from ui.components.leads_view import (
    build_detailed_lead_display,
    build_lead_overall_display,
)

from db.engine import get_engine
from db.repos import lead_repo, vtal_repo
from services import audit_services
from services.lead_status_service import define_lead_status
from clients import addsales_client
from core.state import init_session_state, bump_leads_version, get_leads_query

from ui.sections.general import build_general_info_for_lead
from ui.sections.analysis import (
    build_first_analysis_info_for_lead,
    build_detailed_analysis_info_for_lead,
)
# from ui.sections.serasa import build_serasa_info_for_lead
# from ui.sections.escavador import build_escavador_info_for_lead
# from ui.sections.company import build_company_info_for_lead
# from ui.sections.address import build_address_info_for_lead

from dotenv import load_dotenv
from sqlalchemy import text
from datetime import date, datetime, timedelta
from auth import auth_gate, reset_password


load_dotenv()
inject_badges_css()
init_session_state()

ITEMS_PER_PAGE = 10
CPF_PATTERN = re.compile(r"^\d{3}\.\d{3}\.\d{3}\.-\d{2}$")

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
    "street_view"
}

def _validate_audit_suffix(value: str) -> str:
    if value not in AUDIT_SUFFIXES:
       raise ValueError(f"Invalid audit suffix/field: {value!r}")
    return value


def apply_audit_decision(lead_id: str, decision_label: str, note: str, author_id: str) -> bool:
    """Update the canonical df (in session_state) with the audit decision."""
    df = st.session_state.df_leads
    mask = df["Codigo lead AddSales"].astype(str) == str(lead_id)
    if not mask.any():
        return False
    df.loc[mask, "status"] = decision_label
    df.loc[mask, "audit_note"] = note
    df.loc[mask, "audit_ts"] = pd.Timestamp.utcnow()
    df.loc[mask, "audit_author"] = author_id

    st.session_state.df_leads = df
    return True


def build_overall_metrics(df: pd.DataFrame, end_date) -> None:
    df_local = df.copy() if df is not None else pd.DataFrame()

    if "lead_dt" in df_local.columns:
        df_local['lead_dt'] = pd.to_datetime(df_local['lead_dt'], errors='coerce')

    end_ts = pd.to_datetime(end_date)
    week_start = end_ts - pd.Timedelta(days=7)

    total_leads = int(df_local.shape[0])
    status_col = df_local["status"].fillna("") if "status" in df_local.columns else pd.Series([], dtype=str)

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
    with k1: st.metric("Total de Leads no Período", f"{total_leads:,}".replace(",", "."))
    with k2: st.metric("Leads da Última Semana", f"{novos_leads:,}".replace(",", "."), delta_novos_leads)
    with k3: st.metric("Leads Aprovados", f"{leads_aprovados:,}".replace(",", "."))
    with k4: st.metric("Leads Reprovados", f"{leads_reprovados:,}".replace(",", "."))
    with k5: st.metric("**Leads Abertos**", f"{leads_abertos:,}".replace(",", "."))
    with k6: st.metric("**Leads Auditáveis**", f"{leads_auditaveis:,}".replace(",", "."))

    return


def build_on_register_analysis(lead):
    infomais_analysis = lead['serasa_infomais']


    register_data_columns = st.columns(3)
    with register_data_columns[0]:
        st.caption("Dia reservado para pagemento")

        if lead['payment_day'] is None or pd.isna(lead['payment_day']):
            st.write('—')
        else:
            st.write(str(int(lead['payment_day'])))

    with register_data_columns[1]:
        st.caption("Método de pagamento")

        if lead['payment_method'] is None or pd.isna(lead['payment_method']):
            st.write('—')
        else:
            st.write(lead['payment_method'].title())
    
    with register_data_columns[2]:
        st.caption("Data agendada para Instalação")
        st.write(fmt_date(lead['installation_date']))

    serasa_cols = st.columns(3)
    with serasa_cols[0]:
        st.caption('Resultado preliminar Serasa - Infomais')

        if infomais_analysis is None:
            st.write('—')
        else:
            st.write(f"Risco **{infomais_analysis['riskTriage']['riskCode']}**")

    with serasa_cols[1]:
        st.caption('Data consulta Serasa - Infomais')
        st.write(fmt_date(lead['serasa_infomais_dt']))

    with serasa_cols[2]:
        if infomais_analysis is not None:
            if 'bolsaFamilia' in infomais_analysis:
                st.write(":red[**O lead participa de programas assistênciais do governo**]")
            else:
                st.write(":green[O lead **não** participa de programas assistênciais do governo]")

    st.write(' ')
    if infomais_analysis is not None:
        affinity = 'não ' if infomais_analysis['afinidadeBandaLarga'] == "false" else ''
        color = 'red' if affinity == 'não ' else 'green'

        lead_affinity_desc = f':{color}[**O lead {affinity}possui afinidade com o mercado de Telecom**]'
        st.write(lead_affinity_desc)

    create_decision_structure('Resultado Análise Infomais', 'informais', lead)
    return


def build_identity_analysis(lead):
    identity_data_columns = st.columns(3)
    with identity_data_columns[0]:
        st.caption('CPF Cadastrado')
        st.write(fmt_cpf(lead['cpf']))

    with identity_data_columns[1]:
        st.caption('RG Cadastrado')
        st.write(fmt_rg(lead['rg']))

    with identity_data_columns[2]:
        st.caption('Plataforma para verificação do Score Biométrico')
        st.write('www.brflow.com.br')

    identity_data_columns_bottom = st.columns(2)

    with identity_data_columns_bottom[0]:
        st.caption('Link do documento enviado')
        doc_url = lead['doc_link'] if not pd.isna(lead['doc_link']) else '—'
        st.write(doc_url)
    with identity_data_columns_bottom[1]:
        st.write(' ')
        if lead['stolen_documents'] == {}:
            st.write(":green[**Documentos pessoais não possuem histórico recente de furto**]")
        else:
            st.write(":red[**Documentos pessoais _POSSUEM_ histórico recente de furto**]")          


    create_decision_structure('Resultado Análise Documento Pessoal', 'consumer_doc', lead)
    create_decision_structure('Resultado Análise ClearSale (Biometria + Liveliness)', 'biometrics', lead)

    return


def build_detailed_analysis_info_for_lead(lead):
    st.subheader('Informações Adicionais')

    with st.expander('Análise Histórico Jurídico - Escavador'):
        build_escavador_analysis(lead)

    with st.expander('Análise Completa - Serasa'):
        build_serasa_analysis(lead)

    if lead['cnpj'] is not None:
        with st.expander('Análise Cadastral - CNPJ'):
            build_cnpj_analysis(lead)
    return


def build_cnpj_analysis(lead):

    if lead['doc_situation'] is None:
        st.caption('CNPJ Cadastrado')
        st.write(lead['cnpj'])

        st.error('O CNPJ cadastrado é **INVÁLIDO**!')

        if lead['hzn_corp_doc_result'] != 'reprovado':
            update_audit_step_features(lead['lead_id'], 'reprovado', 'corp_doc')
        return


    cnpj_data_columns = st.columns(4)
    cnpj_result = lead['cnpj_json']

    with cnpj_data_columns[0]:
        st.caption("CNPJ Consultado")
        st.write(fmt_cnpj(cnpj_result['cnpj']))

    with cnpj_data_columns[1]:
        st.caption("Razão Social (R.F.)")
        st.write(cnpj_result['razao_social'])

    with cnpj_data_columns[2]:
        st.caption("Situação cadastral (R.F.)")
        st.write(cnpj_result['descricao_situacao_cadastral'])

    with cnpj_data_columns[3]:
        time_since_opening = (date.today() - datetime.strptime(cnpj_result['data_inicio_atividade'], '%Y-%m-%d').date()).days
        age_message = ':green[**(≥ 90 dias)**]' if time_since_opening >= 90 else ':red[**(< 90 dias)**]'

        st.caption("Data de abertura (R.F.)")
        st.write(f"{fmt_date(cnpj_result['data_inicio_atividade'])} {age_message}")

    st.caption('Comprovante de situação cadastral CNPJ enviado')
    st.write(lead['doc_link_corporate'])

    if time_since_opening < 90 or cnpj_result['descricao_situacao_cadastral'] != 'ATIVA':
        if lead['hzn_corp_doc_result'] != 'reprovado':
            st.error(f"CNPJ Reprovado (Situação cadastral inválida ou < 90 dias) - {fmt_date(date.today())}")
            update_audit_step_features(lead['lead_id'], 'reprovado', 'corp_doc')
        else:
            st.error(f"CNPJ Reprovado (Situação cadastral inválida ou < 90 dias) - {fmt_date(lead['hzn_corp_doc_dt'])}")
    else: 
        create_decision_structure('Resultado Análise Comprovante CNPJ', 'corp_doc', lead)

    return


def build_vtal_analysis(lead):
    if lead['vtal_address'] is None:
        st.warning('Endereço ainda não foi corretamente cadastrado...')
        return

    st.warning('**Importante**: considerar que a análise apresentada leva em consideração todos os complementos existentes para o conjunto CEP + Número')

    address = lead['vtal_address']['address']
    add_df = vtal_repo.fetch_vtal_history(db_engine, address)
        

    with st.expander('Histórico completo de HCs'):
        st.dataframe(add_df, hide_index = True)

    active_client = len(add_df[add_df['Status - V.Tal'] == 'hc_ativo'])
    active_client = ':green[**Não**]' if active_client == 0 else ':red[**Sim**]'

    today = pd.to_datetime('today')
    max_date = today - pd.DateOffset(months=24)

    churn_vol_history = add_df[(add_df['Tipo Churn'] == 'voluntario') & (pd.to_datetime(add_df['Data - Retirada'] )>= max_date)]
    churn_vol_history['Mês Churn'] = churn_vol_history['Mês Churn'].str.replace('M', '').astype(int)

    with st.expander('Histórico de Churn VOL - Últimos 24 meses'):
        st.dataframe(churn_vol_history, hide_index = True)  

    churn_vol_filter = ':green[**Não**]' if len(churn_vol_history[churn_vol_history['Mês Churn'] <= 3]) == 0 else ':red[**Sim**]'

    churn_invol_history = add_df[(add_df['Tipo Churn'] == 'involuntario') & (pd.to_datetime(add_df['Data - Retirada']) >= max_date)]
    churn_invol_history['Mês Churn'] = churn_invol_history['Mês Churn'].str.replace('M', '').astype(int)


    with st.expander('Histórico de Churn INVOL - Últimos 24 meses'):
        st.dataframe(churn_invol_history, hide_index = True)


    churn_invol_filter = ':green[**Não**]' if len(churn_invol_history[churn_invol_history['Mês Churn'] <= 6]) == 0 else ':red[**Sim**]'

    vtal_data_columns = st.columns(3)
    with vtal_data_columns[0]:
        st.caption('Cliente V.Tal Ativo')
        st.write(active_client)

    with vtal_data_columns[1]:
        st.caption('Churn VOL em até 3 meses')
        st.write(churn_vol_filter)

    with vtal_data_columns[2]:
        st.caption('Churn INVOL em até 6 meses')
        st.write(churn_invol_filter)

    create_decision_structure('Resultado Análise Cliente V.Tal', 'vtal_client', lead)
    create_decision_structure('Resultado Análise HCs V.Tal', 'vtal_qty_hc', lead)
    return


def build_escavador_analysis(lead):
    escavador_data_columns = st.columns(2)

    n_processos_reu = lead['active_cases_as_defendant'] if not pd.isna(lead['active_cases_as_defendant']) else 0
    n_processos_criminais = len(lead['active_criminal_cases']) if lead['active_criminal_cases'] is not None else 0

    with escavador_data_columns[0]:
        st.caption('Processo Ativos (como Réu)')
        st.write(str(int(n_processos_reu)))

    with escavador_data_columns[1]:
        st.caption('Processos Criminais Ativos (como Réu)')
        st.write(str(n_processos_criminais))

    if n_processos_criminais == 0:
        if n_processos_reu <= 4:
            if lead['hzn_court_case_result'] != 'aprovado':
                st.success(f"Cliente **aprovado** na análise jurídica (< 5 _Processos Ativos_ como réu) - {fmt_date(date.today())}")
                update_audit_step_features(lead['lead_id'], 'aprovado', 'court_case')
            else:
                st.success(f"Cliente **aprovado** na análise jurídica (< 5 _Processos Ativos_ como réu) - {fmt_date(lead['hzn_court_case_dt'])}")
        else:
            create_decision_structure('Resultado Análise Escavador', 'court_case', lead)
            st.warning('A instalação deste cliente está sujeita à taxa de R$ 199,00.')
    else:
        if lead['hzn_court_case_result'] != 'reprovado':
            st.error(f"Cliente **reprovado** na análise jurídica (> 1 _Processo Criminal_ ativo) - {fmt_date(date.today())}")
            update_audit_step_features(lead['lead_id'], 'reprovado', 'court_case')
        else:
            st.error(f"Cliente **reprovado** na análise jurídica (> 1 _Processo Criminal_ ativo) - {fmt_date(lead['hzn_court_case_dt'])}")

    return


def build_serasa_analysis(lead):

    if lead['statusregistration'] is None:
        st.error('O CPF cadastrado é inválido')
    else:
        dividas = lead['serasa_json']['negativeData']['pefin']

        valor_total = dividas['summary']['balance']
        desc_dividas = dividas['pefinResponse']

        score_serasa = int(lead['credit_score']) if not pd.isna(lead['credit_score']) else '—' 

        serasa_data_columnns = st.columns(4)
        with serasa_data_columnns[0]:
            st.caption('Status CPF')
            st.write(lead['statusregistration'])

        with serasa_data_columnns[1]:
            st.caption('Score SERASA')
            st.write(str(score_serasa))

        with serasa_data_columnns[2]:
            st.caption('Dívidas Comerciais')
            st.write(fmt_monetary_value(valor_total))

        with serasa_data_columnns[3]:
            st.caption('Renda estimada')
            st.write(fmt_monetary_value(lead['renda_estimada']))

        if dividas['summary']['count'] > 0:
            st.write('**Histórico de dívidas**')

            tabela_dividas = build_tabela_dividas(desc_dividas)
            st.dataframe(
                tabela_dividas,
                hide_index=True,
                column_config={
                    "Valor da dívida (R$)": st.column_config.NumberColumn(format='localized'),
                    "Ocorrência da dívida": st.column_config.DateColumn(format='localized')
                }
            )

        if lead['statusregistration'] != 'REGULAR':
            st.write(':red[**Status do CPF reprovado (não _Regular_)**]')

            if lead['hzn_serpro_result'] != 'reprovado':
                update_audit_step_features(lead['lead_id'], 'reprovado', 'serpro')

        else:
            st.write(' ')
            st.write(':green[Status do CPF **aprovado** (_Regular_)]')

            if lead['hzn_serpro_result'] != 'aprovado':
                update_audit_step_features(lead['lead_id'], 'aprovado', 'serpro')

            if valor_total > 100:
                if lead['hzn_serasa_result'] != 'reprovado':
                    st.error(f"Cliente **reprovado** na análise Serasa (dívida > R$ 100,00) - {fmt_date(date.today())}")
                    update_audit_step_features(lead['lead_id'], 'reprovado', 'serasa')
                else:
                    st.error(f"Cliente **reprovado** na análise Serasa (dívida > R$ 100,00) - {fmt_date(lead['hzn_serasa_dt'])}")
            else:
                if score_serasa != '—' and score_serasa >= 450:
                    if lead['hzn_serasa_result'] != 'aprovado':
                        st.success(f"Cliente **aprovado** na análise Serasa - {fmt_date(date.today())}")
                        update_audit_step_features(lead['lead_id'], 'aprovado', 'serasa')
                    else:
                        st.success(f"Cliente **aprovado** na análise Serasa - {fmt_date(lead['hzn_serasa_dt'])}")

                else:
                    create_decision_structure('Resultado Análise Serasa', 'serasa', lead)
                    st.warning('A instalação deste cliente está sujeita à taxa de R$ 199,00.')
                      
    return

def create_decision_structure(title, sufix, lead):

    sufix = _validate_audit_suffix(str(sufix))
    current_status = lead[f'hzn_{sufix}_result']
    lead_id = lead['lead_id']

    if pd.isna(current_status) or current_status == 'pendente':
        index = 0
    elif current_status == 'aprovado':
        index = 1
    else:
        index = 2

    col_desc, col_input, col_save = st.columns([0.8, 1.6, 1])
                        
    with col_desc:
        st.write(f'**{title}:**')
    with col_input:
        sel = st.radio(
            "",
            ["Análise Pendente", "Aprovado", "Reprovado"],
            index=index,
            horizontal=True,
            label_visibility='collapsed',
            key=f'radio_{sufix}'
        )
    with col_save:
        if st.button("Salvar", use_container_width=True, key=f'save_{sufix}'):
            analysis_result_map = {
                'Análise Pendente': 'pendente',
                'Aprovado': 'aprovado',
                'Reprovado': 'reprovado'
            }

            analysis_result = analysis_result_map.get(sel, 'pendente')
            lead_repo.update_audit_step(db_engine, lead_id, sufix, analysis_result)
            
            st.cache_data.clear()
            st.rerun()
    return


def display_audit_filter_decision(title, sufix, lead):
    decision_made = lead[f'hzn_{sufix}_result']

    if decision_made is None or decision_made == 'pendente':
        st.warning(f'**{title}:** Ainda não há decisão da auditoria sobre este filtro.')
    elif decision_made == 'aprovado':
        st.success(f'**{title}:** O **Lead {lead['lead_id']}** foi **aprovado** pela auditoria neste filtro.')
    else:
        st.error(f'**{title}:** O **Lead {lead['lead_id']}** foi **reprovado** pela auditoria neste filtro.')

    return


def build_audit_structure(lead):
    st.subheader('Decisão da Auditoria')

    decision_made = not pd.isna(lead['hzn_final_result'])
    edit_mode = st.session_state.get('new_decision', False)

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
        st.session_state.audit_action = 'pendente'
        st.session_state.new_decision = True
        st.rerun()
    if reject_click:
        st.session_state.audit_action = 'reprovado'
        st.session_state.new_decision = True
        st.rerun()

    if not decision_made or edit_mode:
        if approve:
            st.session_state.new_decision = False
            st.session_state.audit_action = None

            addsales_token = os.getenv("ADDSALES_TOKEN")
            
            payload = {
                "codigo_lead_addsales": lead['addsales_code'],
                "cpf": lead['cpf'],
                "data_auditoria": datetime.now().isoformat(),
                "descricao_pendencias": None,
                "motivos_reprovacao": None,
                "resultado_auditoria": 'aprovado'
            }


            try:
                addsales_client.update_lead(
                    token=addsales_token,
                    lead_id=str(lead["addsales_id"]),
                    payload=payload,
                )
            except Exception as e:
                st.error(f"Erro AddSales: {e}")


        elif st.session_state.audit_action in ('pendente', 'reprovado'):
            note = st.text_area(
                "Observação (obrigatória para registrar a decisão)",
                placeholder="Descreva o motivo…",
                height=110
            )

            if st.button('Enviar análise', use_container_width=True):
                if not note.strip():
                    st.error("A observação é obrigatória para a decisão tomada")
                else:
                    final_decision = st.session_state.audit_action

                    st.session_state.new_decision = False
                    st.session_state.audit_action = None
                    
                    observations = (None, note) if final_decision == 'reprovado' else (note, None)

                    addsales_token = os.getenv("ADDSALES_TOKEN")
            
                payload = {
                    "codigo_lead_addsales": lead['addsales_code'],
                    "cpf": lead['cpf'],
                    "data_auditoria": datetime.now().isoformat(),
                    "descricao_pendencias": observations[0],
                    "motivos_reprovacao": observations[1],
                    "resultado_auditoria": final_decision
                }


                try:
                    addsales_client.update_lead(
                        token=addsales_token,
                        lead_id=str(lead["addsales_id"]),
                        payload=payload,
                    )
                except Exception as e:
                    st.error(f"Erro AddSales: {e}")

                    if response.status_code == 200:
                        update_audit_result_features(lead['lead_id'],
                                              final_decision,
                                              pending_obs=observations[0],
                                              denied_obs=observations[1])
                    else:
                        st.error(response.status_code)   
    
    if decision_made:
        fmt_status = lead['status'].split(' - ')[0]
        color = 'red' if fmt_status == 'Reprovado' else ('yellow' if fmt_status == 'Pendente' else 'green')

        st.info(f"Lead já auditado. Decisão feita: :{color}[**{fmt_status}**] - :{color}[**{fmt_date(lead['hzn_final_result_dt'])}**]")

        if not edit_mode:
            if lead['hzn_final_result'] == 'pendente':
                st.info(f"Motivos registrados: {lead['hzn_pending']}")
            elif lead['hzn_final_result'] == 'reprovado':
                st.info(f"Motivos registrados: {lead['hzn_denied']}")

            if st.button("Editar decisão", use_container_width=True):
                st.session_state.new_decision = True
                st.rerun()
        else:
           if st.button("**Cancelar edição**", use_container_width=True, type='primary'):
                st.session_state.new_decision = False
                st.rerun() 

    return


def display_final_audit_decision(lead):
    decision_made = lead[f'hzn_final_result']

    if decision_made is None or decision_made == 'pendente':
        st.warning(f'Ainda não há decisão da auditoria sobre este lead.')
    elif decision_made == 'aprovado':
        st.success(f'O **Lead {lead['lead_id']}** foi **aprovado** pela auditoria como cliente.')
    else:
        st.error(f'O **Lead {lead['lead_id']}** foi **reprovado** pela auditoria como cliente.')    

    return


def update_audit_step_features(lead_id, decision, field):
    field = _validate_audit_suffix(str(field))
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

    st.cache_data.clear()
    st.rerun()
    return


st.set_page_config(page_title="SalesLab", page_icon="🔬", layout="wide")
authenticator = auth_gate()

if st.session_state.get('authentication_status'):
    st.title('Histórico de Leads - SalesLab')

    with st.sidebar:
        name = st.session_state.name
        username = st.session_state.username

        st.markdown(f"**Olá, {name}** 👋")
        authenticator.logout("Sair", "sidebar")


    c1, c2, c3 = st.columns([1.2,1,1])
    with c1:
        st.subheader("Resumo de Leads")
    with c2:
        start = st.date_input("Início", date.today() - timedelta(days=30), format='DD/MM/YYYY')
    with c3:
        end = st.date_input("Fim", date.today(), format='DD/MM/YYYY')

    db_engine = get_engine('local')

    df_leads = lead_repo.fetch_leads(db_engine, d_start=start, d_end=end)
    df_leads = fmt_leads_features(df_leads)

    if len(df_leads) == 0:
        st.error('No intervalo escolhido não existe nenhum lead...')
    else:
        df_leads['status'] = df_leads.apply(define_lead_status, axis=1)
        df_leads = df_leads.sort_values("lead_dt", ascending=False)

        build_overall_metrics(df_leads, end)

        if st.button('**Atualizar Leads**', use_container_width=True, icon='🔄', type='tertiary'):
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
                render_first_analysis=build_first_analysis_info_for_lead,
                render_detailed_analysis=build_detailed_analysis_info_for_lead,
                render_audit=build_audit_structure,
        )

else:
    st.write(st.session_state.get('authentication_status'))
    pass