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

# --- FUNÇÃO AUXILIAR: GESTÃO DE RECADOS (FILTRADA POR DATA) ---
def gerenciar_recados():
    st.title("📌 Recados de Hoje")
    
    # Botão de Novo Cadastro (Útil para o tablet)
    st.link_button("➕ Cadastrar Novo Recado", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        
        if not dados:
            st.warning("Nenhum registro encontrado na planilha.")
            return

        df = pd.DataFrame(dados)

        # --- LÓGICA DE FILTRO POR DATA ATUAL ---
        # 1. Identifica a Coluna A (índice 0) e converte para data pura (ignorando horas)
        col_data = df.columns[0]
        df[col_data] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce').dt.date
        
        # 2. Obtém a data de hoje
        hoje = datetime.now().date()
        
        # 3. Filtra o DataFrame para mostrar apenas o que for IGUAL a hoje
        df_filtrado = df[df[col_data] == hoje].copy()

        if df_filtrado.empty:
            st.info(f"📅 Não há recados lançados para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # --- CONFIGURAÇÃO DE COLUNAS ---
        col_b = df_filtrado.columns[1] # Quem pede
        col_c = df_filtrado.columns[2] # Recado
        
        if "Aprovação" not in df_filtrado.columns:
            df_filtrado["Aprovação"] = True
        else:
            df_filtrado["Aprovação"] = df_filtrado["Aprovação"].apply(lambda x: True if str(x) in ['1', 'True', 'VERDADEIRO'] else False)

        # --- EXIBIÇÃO EM CARDS COLORIDOS (OTIMIZADO PARA TABLET) ---
        st.write(f"Filtrado para: **{hoje.strftime('%d/%m/%Y')}**")
        
        for i, row in df_filtrado.iterrows():
            cor_fundo = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            status_simbolo = "✅" if row["Aprovação"] else "❌"
            
            st.markdown(f"""
                <div style="background-color: {cor_fundo}; padding: 20px; border-radius: 15px; margin-bottom: 12px; border: 2px solid rgba(0,0,0,0.1); color: #0e2433;">
                    <div style="font-size: 18px; font-weight: bold; margin-bottom: 5px;">{status_simbolo} {row[col_b]}</div>
                    <div style="font-size: 20px; line-height: 1.4;">{row[col_c]}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # --- PAINEL DE EDIÇÃO ---
        st.subheader("Controle de Status")
        # Mostramos apenas Aprovação, Quem pede e Recado no editor
        df_para_editar = df_filtrado[["Aprovação", col_b, col_c]]
        
        df_editado = st.data_editor(
            df_para_editar,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                col_b: "Solicitante",
                col_c: "Conteúdo do Recado"
            },
            key="ed_recados_hoje"
        )

        if st.button("💾 ATUALIZAR STATUS", use_container_width=True):
            with st.spinner("Gravando..."):
                # Atualiza o DF original com as mudanças do filtrado
                df.loc[df_filtrado.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                
                aba.clear()
                aba.update([df.columns.values.tolist()] + df.values.tolist())
                st.success("Atualizado!")
                time.sleep(1)
                st.rerun()

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

# --- ATUALIZAÇÃO DO ROTEAMENTO ---
if sel == "Recados":
    gerenciar_recados()

elif sel == "Apresentação":
    st.title("📢 Tela de Apresentação (Telão)")
    st.info("Área em construção...")

# (Outras opções seguem o mesmo padrão por enquanto)
else:
    st.title(f"ℹ️ {sel}")
    st.info("Aguardando configuração de dados...")