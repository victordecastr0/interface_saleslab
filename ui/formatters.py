from __future__ import annotations

import pandas as pd


def fmt_date(d) -> str:
    return "—" if pd.isna(d) else pd.to_datetime(d).strftime("%d/%m/%Y")


def fmt_monetary_value(v) -> str:
    """
    Format monetary values to Brazilian format: R$ 1.234,56
    Accepts numeric values or strings.
    """
    if pd.isna(v):
        return "—"

    if isinstance(v, (int, float)):
        value = float(v)
    else:
        s = str(v).strip()
        s = s.replace("R$", "").replace(" ", "")
        s = s.replace(".", "").replace(",", ".")

        try:
            value = float(s)
        except ValueError:
            return str(v)

    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_cpf(c) -> str:
    fmt_c = str(c).strip().replace(".", "").replace("-", "")

    if len(fmt_c) != 11:
        return fmt_c

    return f"{fmt_c[:3]}.{fmt_c[3:6]}.{fmt_c[6:9]}-{fmt_c[9:11]}"


def fmt_cnpj(c) -> str:
    fmt_c = str(c).strip().replace(".", "").replace("-", "")

    if len(fmt_c) != 14:
        return fmt_c

    return f"{fmt_c[0:2]}.{fmt_c[2:5]}.{fmt_c[5:8]}/{fmt_c[8:12]}-{fmt_c[12:]}"


def fmt_rg(r) -> str:
    if r is None:
        return "—"

    fmt_r = str(r).strip().replace(".", "").replace("-", "")

    if len(fmt_r) != 7:
        return fmt_r

    return f"{fmt_r[:3]}.{fmt_r[3:6]}-{fmt_r[6:]}"


def fmt_zipcode(z) -> str:
    z = str(z)
    if len(z) < 8:
        return z
        
    return f"{z[:2]}.{z[2:5]}-{z[5:]}"


def fmt_leads_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preenche campos do lead a partir do serasa_json quando estiverem faltando.
    """
    fmt_df = df.copy()

    for i, row in fmt_df.iterrows():
        if not pd.isna(row.get("name")):
            continue

        cpf = row.get("cpf")
        serasa = row.get("serasa_json")

        if (not pd.isna(cpf)) and (not pd.isna(serasa)) and isinstance(serasa, dict) and ("registration" in serasa):
            reg = serasa["registration"] or {}
            fmt_df.at[i, "name"] = reg.get("consumerName")
            fmt_df.at[i, "mothersname"] = reg.get("motherName")
            fmt_df.at[i, "birth_dt"] = reg.get("birthDate")
        elif not pd.isna(cpf):
            fmt_df.at[i, "name"] = f"CPF: {fmt_cpf(cpf)}"
        else:
            fmt_df.at[i, "name"] = "Documento não fornecido"

    return fmt_df