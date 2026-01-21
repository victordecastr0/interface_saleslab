from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def fetch_vtal_history(engine: Engine, address: dict) -> pd.DataFrame:
    """
    Fetch vtal HCs history.
    """
    query = text(
        """
        SELECT
            vhc.zip AS "CEP",
            vhc.number AS "Número",
            CONCAT_WS(', ', vhc.address_detail_1, vhc.address_detail_2, vhc.address_detail_3)  AS "Complemento",
            vhc.city AS "Cidade",
            vhc.tenant AS "Tenant",
            vhc.order_dt AS "Data - Ordem",
            vhc.installation_dt AS "Data - Instalacão",
            vhc.pickup_dt AS "Data - Retirada",
            vhc.churn_month AS "Mês Churn",
            vcl.churn_type AS "Tipo Churn",
            vcl.status AS "Status - V.Tal",
            vcl.last_block_dt as "Último bloqueio"
        FROM vtal_homeconnection_v2 vhc
            JOIN vtal_customer_life_v2 vcl on vhc.hc = vcl.hc 
        WHERE vhc.zip = :zip_code AND vhc.number = :number
        ORDER BY "Data - Ordem" DESC, "Data - Instalacão" DESC;
        """
    )

    with engine.begin() as conn:
        hc_history_df = pd.read_sql(
            query,
            conn,
            params = {"zip_code": address.get('zipCode'), "number": address.get('number')}
        )

    hc_history_df = hc_history_df.replace(' ', None)
    return hc_history_df