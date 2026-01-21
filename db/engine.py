from __future__ import annotations

import os

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@st.cache_resource
def get_engine(env: str = "local") -> Engine:
    """
    Return a SQLAlchemy engine.
    Keep this cached at the resource layer (Streamlit).
    """
    if env != "local":
        raise ValueError(f"Unsupported env: {env!r}")

    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL not found in environment")

    return create_engine(db_url, pool_pre_ping=True)