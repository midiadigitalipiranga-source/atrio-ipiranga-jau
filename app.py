import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time
import pytz
# --- FUNÇÃO AUXILIAR PARA OBTER DATA BRASIL ---
def obter_hoje_brasil():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).date()

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


# --- MÓDULO DE RECADOS ---

def gerenciar_recados():
    st.title("📌 Recados de Hoje")
    st.link_button("➕ Novo Cadastro (Forms)", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Sem recados para hoje.")
            return

        # --- LÓGICA DE AUTO-APROVAÇÃO (CORREÇÃO) ---
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            # Se o valor for vazio, 1, True ou VERDADEIRO, vira True. Se for 0 ou False, vira False.
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(
                lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True
            )

        col_b = df_hoje.columns[1] 
        col_c = df_hoje.columns[2] 

        # Cards de Visualização
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f'<div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);"><div style="font-size: 14px; font-weight: bold;">{row[col_b]}</div><div style="font-size: 16px;">{row[col_c]}</div></div>', unsafe_allow_html=True)

        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_b, col_c]],
            use_container_width=True, hide_index=True,
            column_config={"Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small")},
            key="ed_recados"
        )

        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
            df_original.loc[df_hoje.index, col_b] = df_editado[col_b]
            df_original.loc[df_hoje.index, col_c] = df_editado[col_c]
            
            df_para_salvar = df_original.copy()
            df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
            aba.clear()
            aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
            st.success("✅ Sincronizado!")
            time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- MÓDULO DE VISITANTES ---

def gerenciar_visitantes():
    st.title("🫂 Visitantes de Hoje")
    st.link_button("➕ Novo Visitante", "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_visitante")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhum visitante para hoje.")
            return

        # Lógica de Aprovação (Vazio = Ativo)
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True)

        col_nome = df_hoje.columns[1]   # Nome do Visitante
        col_igreja = df_hoje.columns[2] # Igreja
        col_convite = df_hoje.columns[3] # Quem convidou

        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f'<div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433;"><div style="font-size: 16px; font-weight: bold;">👤 {row[col_nome]}</div><div style="font-size: 14px;">Igreja: {row[col_igreja]} | Convidado por: {row[col_convite]}</div></div>', unsafe_allow_html=True)

        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_nome, col_igreja, col_convite]],
            use_container_width=True, hide_index=True,
            column_config={"Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small")},
            key="ed_visitantes"
        )

        if st.button("💾 SALVAR VISITANTES", use_container_width=True):
            df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
            df_original.loc[df_hoje.index, col_nome] = df_editado[col_nome]
            
            df_para_salvar = df_original.copy()
            df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
            aba.clear()
            aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
            st.success("✅ Visitantes Atualizados!")
            time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- ATUALIZAÇÃO DO ROTEAMENTO ---
if sel == "Recados":
    gerenciar_recados()

elif sel == "Visitantes":
    gerenciar_visitantes()

elif sel == "Ausência":
    st.title("📉 Ausências")
    st.info("Aguardando configuração de dados para esta aba...")

elif sel == "Oração":
    st.title("🙏 Pedidos de Oração")
    st.info("Aguardando configuração de dados para esta aba...")

elif sel == "Parabenização":
    st.title("🎂 Parabenização")
    st.info("Aguardando configuração de dados para esta aba...")

elif sel == "Programação":
    st.title("🗓️ Programação")
    st.info("Aguardando configuração de dados para esta aba...")

elif sel == "Apresentação":
    # Aqui chamaremos a tela de leitura final para o tablet
    st.title("📢 Tela de Apresentação")
    st.info("Aguardando configuração de dados para esta aba...")