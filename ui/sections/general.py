import streamlit as st

from ui.tables import build_tabela_telefones
from ui.components.leads_view import status_badge
from ui.formatters import (
    fmt_date,
    fmt_cpf,
    fmt_rg,
    fmt_monetary_value,
)


def build_general_info_for_lead(lead):
    st.markdown(f"### **{lead['name'].title()}**    " + status_badge(lead['status']), unsafe_allow_html=True)

    with st.expander("Identificadores", expanded=False):
        columns_ids = st.columns(5)

        with columns_ids[0]:
            st.caption('Lead ID')
            st.code(lead['lead_id'], language=None)
        with columns_ids[1]:
            st.caption('Código Lead - AddSales')
            st.code(lead['addsales_code'], language=None)
        with columns_ids[2]:
            inventory_payload = lead.get('vtal_availability')
            inventory_id = (
                inventory_payload.get('resource', {}).get('inventoryId')
                if isinstance(inventory_payload, dict)
                else None
            )

            st.caption('Inventory ID - V.Tal')
            st.code(inventory_id, language=None)
        with columns_ids[3]:
            address_payload = lead.get('vtal_address')
            address_id = (
                address_payload.get('address', {}).get('id')
                if isinstance(address_payload, dict)
                else None
            )

            st.caption('Address ID - V.Tal')
            st.code(address_id, language=None)
        with columns_ids[4]:
            st.caption('Ordem de Instalação - V.Tal')
            st.code(lead['vtal_order_installation'], language=None)

    core_columns_top = st.columns(5)
    with core_columns_top[0]:
        st.caption("Criado em")
        st.write(fmt_date(lead['lead_dt']))
    with core_columns_top[1]:
        st.caption("Tenant responsável")
        st.write(lead['tenant'])
    with core_columns_top[2]:
        st.caption('Campanha de origem')
        st.write(lead['campaign'])
    with core_columns_top[3]:
        plan_name = lead['plan_result']
        plan_name = plan_name['name'] if plan_name is not None else None

        st.caption('Plano selecionado')
        st.write(plan_name)
    with core_columns_top[4]:
        plan_price = lead['plan_result']
        plan_price = plan_price['price'] if plan_price is not None else None

        st.caption('Valor do Plano Selecionado')
        st.write(fmt_monetary_value(plan_price))

    core_columns_bottom = st.columns(3)
    with core_columns_bottom[0]:
        st.caption('E-mail cadastrado')
        st.write(lead['email'])
    with core_columns_bottom[1]:
        st.caption('Filiação')

        if lead["fathersname"] is None:
            st.write(f"{lead['mothersname']} (Mãe)")
        elif lead["mothersname"] is None:
            st.write(f"{lead['fathersname']} (Pai)")
        else:
            st.write(f"{lead['fathersname']} & {lead['mothersname']}")
    with core_columns_bottom[2]:
        st.caption('Senha para acesso de documentos')
        st.code(lead['doc_link_password'], language=None)


    with st.expander('_Últimos telefones registrados - Serasa_'):
        if lead['all_phones'] is not None:
            st.table(build_tabela_telefones(lead['all_phones']), border='horizontal')
        else:
            st.write(":red[**O lead não possui telefones registrados no Serasa...**]")

    st.divider()
