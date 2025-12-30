import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- 2. ESTILO VISUAL (Sidebar Azul e Botões Amarelos) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0e2433; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stApp { background-color: #f0f2f6; }
    .stButton > button { background-color: #ffc107; color: #0e2433; border-radius: 10px; font-weight: bold; }
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center;'>🔐 Átrio - Acesso</h1>", unsafe_allow_html=True)
        senha = st.text_input("Digite a senha administrativa:", type="password")
        if st.button("Entrar", use_container_width=True):
            if senha == st.secrets["acesso"]["senha_admin"]:
                st.session_state["logado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- 4. CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar():
    cred = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    cred['private_key'] = cred['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(cred)
    # Sua Planilha Mestra
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- 5. MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True)
    sel = option_menu(
        menu_title=None,
        options=["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "Apresentação"],
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "cast"],
        default_index=0,
        styles={
            "container": {"background-color": "#0e2433"},
            "nav-link": {"color": "white", "font-size": "16px", "text-align": "left"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}
        }
    )

# --- 6. ROTEAMENTO INICIAL ---
if sel == "Recados":
    st.title("📌 Gestão de Recados")
    st.info("Área em construção...")

elif sel == "Apresentação":
    st.title("📢 Tela de Apresentação (Telão)")
    st.info("Área em construção...")

# (Outras opções seguem o mesmo padrão por enquanto)
else:
    st.title(f"ℹ️ {sel}")
    st.info("Aguardando configuração de dados...")