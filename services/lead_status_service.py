from __future__ import annotations


def define_lead_status(row):
    """
    Define lead status based on audit and AddSales fields.
    Logic moved verbatim from UI layer (no behavior change).
    """
    
    if row['hzn_audit']:
        if row['hzn_final_result'] is None:
            return 'Necessária auditoria'
        else:
            return f"{row['hzn_final_result'].title()} - Auditoria"

    if row['homeativo_status'] == 'Venda aprovada':
        return 'Aprovado'

    if row['homeativo_status'] == 'Reprovado':
        return 'Reprovado - AddSales'

    return 'Em Negociação - AddSales'