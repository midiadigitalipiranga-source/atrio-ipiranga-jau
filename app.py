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

# --- FUNÇÃO AUXILIAR: GESTÃO DE RECADOS ---
def gerenciar_recados():
    st.title("📌 Gestão de Recados")
    
    # Botão de Novo Cadastro (Sempre visível)
    st.link_button("➕ Cadastrar Novo Recado (Forms)", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        
        if not dados:
            st.warning("Nenhum recado encontrado.")
            return

        df = pd.DataFrame(dados)

        # 1. Selecionar apenas Colunas B e C (índices 1 e 2)
        # Assumindo: Col B = Quem pede, Col C = Recado
        col_b = df.columns[1]
        col_c = df.columns[2]
        
        # 2. Criar/Verificar coluna de Aprovação (Flag)
        if "Aprovação" not in df.columns:
            df["Aprovação"] = True  # Inicia aprovado (1)
        else:
            # Converte valores da planilha para Booleano (True/False)
            df["Aprovação"] = df["Aprovação"].apply(lambda x: True if str(x) in ['1', 'True', 'VERDADEIRO'] else False)

        # 3. Preparar DataFrame para exibição (Aprovação na frente)
        df_display = df[["Aprovação", col_b, col_c]]

        # --- VISUALIZAÇÃO COLORIDA (PARA CELULAR) ---
        st.markdown("### Visualização de Status")
        for i, row in df_display.iterrows():
            cor_fundo = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            status_texto = "✅ APROVADO" if row["Aprovação"] else "❌ REPROVADO"
            
            st.markdown(f"""
                <div style="background-color: {cor_fundo}; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #ccc; color: #333;">
                    <div style="font-size: 10px; font-weight: bold;">{status_texto}</div>
                    <div style="font-size: 14px; font-weight: bold;">{row[col_b]}</div>
                    <div style="font-size: 16px;">{row[col_c]}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Painel de Controle (Edição)")
        
        # 4. Editor com fonte e Checkbox grande para celular
        df_editado = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn(
                    "Aprovar?",
                    help="Marque para exibir no telão",
                    default=True,
                    width="medium" # Deixa a coluna mais larga para o polegar
                ),
                col_b: st.column_config.TextColumn("Quem pede", width="medium"),
                col_c: st.column_config.TextColumn("Recado", width="large"),
            },
            key="editor_recados"
        )

        # 5. Botão de Salvar
        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            with st.spinner("Atualizando planilha..."):
                # Mesclar edições de volta ao dataframe original
                df.update(df_editado)
                # Converter Booleano de volta para 1 e 0 para o Google Sheets
                df["Aprovação"] = df["Aprovação"].apply(lambda x: 1 if x else 0)
                
                # Atualizar Planilha
                aba.clear()
                aba.update([df.columns.values.tolist()] + df.values.tolist())
                st.success("Planilha atualizada com sucesso!")
                time.sleep(1)
                st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar aba 'cadastro_recados': {e}")

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