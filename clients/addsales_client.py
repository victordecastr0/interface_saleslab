from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class AddSalesResponse:
    status_code: int
    body_text: str


class AddSalesError(RuntimeError):
    pass


def update_lead(
    *,
    token: str,
    addsales_code: str,
    payload: Dict[str, Any],
    timeout_s: int = 20,
    headers: Optional[Dict[str, str]] = None,
) -> AddSalesResponse:
    """
    Minimal HTTP client for AddSales update.
    Behavior: raises on non-2xx to make failures explicit.
    """
    if not token:
        raise AddSalesError("token vazio")
    if not addsales_code:
        raise AddSalesError("addsales_code vazio")

    url = f"https://facilito.promo/planos/hzn/audit/result?token={token}"

    headers = headers or {"Content-Type": "application/json"}

    try:
        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        raise AddSalesError(f"falha HTTP AddSales: {e}") from e

    if not (200 <= r.status_code < 300):
        msg = f"AddSales retornou {r.status_code}: {r.text}"
        raise AddSalesError(msg)

    return AddSalesResponse(status_code=r.status_code, body_text=r.text)
