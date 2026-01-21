from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st


def build_tabela_enderecos(descricao_enderecos):
    if descricao_enderecos == "{}":
        st.error("Não há registro de endereços ligados à este CPF")
        return None

    info_enderecos = descricao_enderecos.replace("{", "").replace("}", "")
    info_enderecos = info_enderecos.split('","')
    info_enderecos = [e.replace('"', "").replace("\\", "") for e in info_enderecos]

    enderecos = []
    register_data = []

    for desc in info_enderecos:
        endereco, reg_data = desc.replace("(", "").replace(")", "").split(",")

        enderecos.append(endereco)
        register_data.append(datetime.strptime(reg_data, "%Y-%m-%d"))

    address_history_df = pd.DataFrame({"Endereço registrado": enderecos, "Data de registro": register_data})
    address_history_df = address_history_df.sort_values(by="Data de registro", ascending=False)
    address_history_df["Data de registro"] = address_history_df["Data de registro"].dt.strftime("%d de %B de %Y")
    address_history_df.index = address_history_df.index + 1

    return address_history_df


def build_tabela_telefones(phone_data_string):
    if phone_data_string == "{}":
        st.error("Não há registro de telefones ligados à este CPF")
        return None

    phone_data_string_fmt = phone_data_string.replace("{", "").replace("}", "")
    all_phone_data = phone_data_string_fmt.split('","')
    all_phone_data = [p.replace('"', "") for p in all_phone_data]

    phones = []
    register_data = []

    for phone_data in all_phone_data:
        phone, reg_data = phone_data.replace("(", "").replace(")", "").split(",")
        phone = f"({phone[:2]}) {phone[2:]}"

        phones.append(phone)
        register_data.append(datetime.strptime(reg_data, "%Y-%m-%d"))

    phone_history_df = pd.DataFrame({"Número registrado": phones, "Data de registro": register_data})
    phone_history_df = phone_history_df.sort_values(by="Data de registro", ascending=False)
    phone_history_df["Data de registro"] = phone_history_df["Data de registro"].dt.strftime("%d de %B de %Y")
    phone_history_df.index = phone_history_df.index + 1

    return phone_history_df


def build_tabela_dividas(descricao_dividas):
    fmt_debt_data = []
    
    for debt in descricao_dividas:
        new_debt = {
            'Credor': debt['creditorName'],
            'Natureza da dívida': debt['legalNature'],
            'Valor da dívida (R$)': debt['amount'],
            'Ocorrência da dívida': debt['occurrenceDate']
        }

        fmt_debt_data.append(new_debt)

    debt_df = pd.DataFrame(fmt_debt_data) 
    debt_df = debt_df.sort_values(by='Ocorrência da dívida', ascending=False)
    return debt_df