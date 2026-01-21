import streamlit as st

import ui.sections.address_hepers as address


def build_first_analysis_info_for_lead(lead):
    st.subheader('Informações Básicas')

    with st.expander("Análise Cadastral"):
        build_on_register_analysis(lead)

    with st.expander("Análise Viabilidade - V.Tal"):
        address.build_availability_analysis(lead)

    with st.expander('Comprovação de Identidade'):
        build_identity_analysis(lead)

    with st.expander('Comprovação de Endereço'):
        address.build_address_analysis(lead)

    with st.expander('Análise Histórico - V.Tal'):
        address.build_vtal_analysis(lead)

    with st.expander('Análise Google Street View'):
        address.buiild_street_view_analysis(lead)

    st.divider()


def build_detailed_analysis_info_for_lead(lead):
    st.subheader("Análise detalhada")

    st.write(f"Resultado auditoria: {lead.get('hzn_final_result')}")
    st.write(f"Auditoria ativa: {lead.get('hzn_audit')}")