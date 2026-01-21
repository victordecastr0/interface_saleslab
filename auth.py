"""
auth.py — Streamlit authentication helper using streamlit-authenticator.

Responsibilities:
- Load & persist config (usernames, hashed passwords, cookie settings, preauthorized emails)
- Render login UI
- Toggle and render register UI when "Criar nova conta" is pressed
- Toggle and render forgot password UI when "Gerar nova senha" is pressed
- Return (name, auth_status, username, authenticator) to the caller
"""

import yaml

import streamlit as st
import streamlit_authenticator as stauth

from time import sleep
from pathlib import Path
from yaml.loader import SafeLoader


DEFAULT_CONFIG_PATH = Path("config.yaml")

def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.load(f, Loader=SafeLoader)

    return None


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, sort_keys=False, allow_unicode=True)

    return


def _build_authenticator(config: dict) -> stauth.Authenticate:
    return stauth.Authenticate(
        credentials=config["credentials"],
        cookie_name=config["cookie"]["name"],
        key=config["cookie"]["key"],
        cookie_expiry_days=config["cookie"]["expiry_days"],
        api_key = config["api_key"],
        auto_hash=False
    )

def auth_gate(
    config_path: Path = DEFAULT_CONFIG_PATH,
    title: str = "🔐 Acesso - SalesLab"
):
    if st.session_state.get('authentication_status'):
        config = load_config(config_path)
        return _build_authenticator(config)
        
    st.title(title)

    if "auth_ui" in st.session_state:
        if st.session_state.auth_ui is None:
            st.session_state.auth_ui = 'LOGIN'

    if st.session_state.get('authentication_status') is False:
        st.error('Senha incorreta')

    if "auth_ui" not in st.session_state:
        st.session_state.auth_ui = 'LOGIN'

    config = load_config(config_path)
    authenticator = _build_authenticator(config)

    name = username = None
    auth_status = None

    if st.session_state.auth_ui == 'LOGIN':
        login_page_ui(authenticator)

    elif st.session_state.auth_ui == 'FIRST_ACCESS':
        first_access_ui(authenticator, config, config_path)        

    elif st.session_state.auth_ui == 'FORGOT_PASSWORD':
        forgot_password_ui(authenticator, config, config_path)
        

    if st.session_state.get('authentication_status'):
        st.session_state.auth_ui = None
        return authenticator

    return None


def login_page_ui(authenticator):
    try:
        authenticator.login(
            location="main",
            captcha=True,
            single_session=True,
            fields={
                'Form name': 'Login - SalesLab',
                'Username': 'Email cadastrado',
                'Password': 'Senha'
            }
        )
    except Exception as e:
        st.error(e)

    cols = st.columns([1, 1])
    with cols[0]:
        st.markdown("**Primeiro acesso?**")
        if st.button("Criar nova conta", use_container_width=True):
            st.session_state.auth_ui = 'FIRST_ACCESS'
            st.rerun()

    with cols[1]:
        st.markdown("**Esqueceu a senha?**")
        if st.button("Gerar nova senha", use_container_width=True):
            st.session_state.auth_ui = 'FORGOT_PASSWORD'
            st.rerun()

    return


def first_access_ui(authenticator, config, config_path):
    try:
        email, username_new, name_new = authenticator.register_user(
            pre_authorized=config["pre-authorized"]["emails"],
            location="main",
            merge_username_email=True,
            password_hint=False,
            fields={
                'Form name': 'Criacão de novo usuário',
                'First name': 'Nome',
                'Last name': 'Sobrenome',
                'Password': 'Senha',
                'Repeat password': 'Repita a senha'
            }
        )

        if email:
            st.success("✅ Usuário criado com sucesso!")
            save_config(config, config_path)
            sleep(1.5)

            st.session_state.auth_ui = 'LOGIN'
            st.rerun()

    except Exception as e:
        st.error(e)

    if st.button("Voltar ao login", use_container_width=True):
        st.session_state.auth_ui = 'LOGIN'
        st.rerun()

    return

def forgot_password_ui(authenticator, config, config_path):
    username_of_forgotten_password, \
    email_of_forgotten_password, \
    new_random_password = authenticator.forgot_password(
        send_email=True,
        fields={
            'Form name': 'Esqueceu a senha?',
            'Username': 'Email cadastrado'
        }
    )
    st.write(email_of_forgotten_password)
    if username_of_forgotten_password:
        save_config(config, config_path)
        st.success(f'Uma nova senha aleatória foi gerada e enviada para o email {email_of_forgotten_password}!')
        st.success('Use a nova senha para efetuar o login! Após efetuado, será possível alterar a senha.')
    elif email_of_forgotten_password is None:
        st.error('Email não registrado')

    cols = st.columns([1, 1])
    with cols[0]:
        if st.button("Voltar ao login", use_container_width=True):
            st.session_state.auth_ui = 'LOGIN'
            st.rerun()

    with cols[1]:
        if st.button("Criar nova conta", use_container_width=True):
            st.session_state.auth_ui = 'FIRST_ACCESS'
            st.rerun()

    return

def reset_password(authenticator, username):
    config = load_config(DEFAULT_CONFIG_PATH)

    try:
        if authenticator.reset_password(username):
            save_config(config)
            st.success("Senha alterada com sucesso.")
    except Exception as e:
        st.error(e)

    return
