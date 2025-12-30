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

# --- FUNÇÃO AUXILIAR: GESTÃO DE RECADOS (FILTRADA POR DATA) ---

def gerenciar_recados():
    st.title("📌 Recados de Hoje")
    
    # Botão de Novo Cadastro
    st.link_button("➕ Novo Cadastro (Forms)", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        # Pega todos os dados da planilha
        dados = aba.get_all_records()
        
        if not dados:
            st.warning("A planilha parece estar vazia.")
            return

        df_original = pd.DataFrame(dados)

        # 1. TRATAMENTO DE DATA (Fuso Brasil)
        col_data = df_original.columns[0]
        # Converte a coluna A para data pura, tratando erros
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        
        hoje = obter_hoje_brasil()
        
        # 2. FILTRAGEM (Cria uma cópia apenas de hoje para trabalhar)
        # Filtramos comparando apenas as datas (dt.date)
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhum recado para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # 3. VERIFICAÇÃO DA COLUNA APROVAÇÃO
        # Se não existir a coluna na planilha, o programa cria e marca como aprovado (1)
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
            df_original["Aprovação"] = 1
        else:
            # Converte o que vem da planilha (1 ou 0) para True/False para o editor do Streamlit
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(lambda x: True if str(x) in ['1', 'True', 'VERDADEIRO'] else False)

        # 4. EXIBIÇÃO VISUAL (TABLET)
        col_b = df_hoje.columns[1] # Solicitante
        col_c = df_hoje.columns[2] # Recado

        for i, row in df_hoje.iterrows():
            cor_fundo = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            status_ico = "✅" if row["Aprovação"] else "❌"
            st.markdown(f"""
                <div style="background-color: {cor_fundo}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);">
                    <div style="font-size: 13px; font-weight: bold; opacity: 0.7;">{status_ico} STATUS ATUAL</div>
                    <div style="font-size: 14px; font-weight: bold;">{row[col_b]}</div>
                    <div style="font-size: 16px;">{row[col_c]}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("### ⚙️ Painel de Aprovação")
        
        # 5. EDITOR DE DADOS (Interação com o usuário)
        # Ocultamos a data (Col A) para não poluir o tablet
        df_para_editar = df_hoje[["Aprovação", col_b, col_c]]
        
        df_editado = st.data_editor(
            df_para_editar,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                col_b: st.column_config.TextColumn("Solicitante", disabled=True),
                col_c: st.column_config.TextColumn("Recado", disabled=True),
            },
            key="ed_recados_save"
        )

        # 6. BOTÃO SALVAR (ENVIA PARA O GOOGLE SHEETS)
        if st.button("💾 SALVAR ALTERAÇÕES NA PLANILHA", use_container_width=True):
            with st.spinner("Sincronizando com Google Sheets..."):
                # Atualizamos o dataframe original baseado no que foi editado na tela de "Hoje"
                # Localizamos os índices originais para garantir que a linha certa seja alterada
                df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                
                # Prepara os dados para envio (converte tudo para string para evitar erros de JSON)
                # Garante que a data original volte formatada corretamente para a planilha
                df_para_salvar = df_original.copy()
                df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
                
                # Limpa a aba e sobe os dados novos
                aba.clear()
                aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                
                st.success("✅ Alterações gravadas com sucesso no Google Sheets!")
                time.sleep(1)
                st.rerun()

    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")

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