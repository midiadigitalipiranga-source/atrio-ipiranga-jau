import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0e2433; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stApp { background-color: #f0f2f6; }
    .stButton > button { background-color: #ffc107; color: #0e2433; border-radius: 10px; font-weight: bold; }
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }
    .agenda-card { background-color: white; padding: 20px; border-radius: 10px; border-left: 8px solid #0e2433; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    .texto-destaque { font-size: 30px; font-weight: bold; color: #0e2433; }
    .texto-normal { font-size: 20px; color: #555; }
</style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center;'>🔐 Átrio - Login</h1>", unsafe_allow_html=True)
        senha = st.text_input("Senha:", type="password")
        if st.button("Entrar", use_container_width=True):
            if senha == st.secrets["acesso"]["senha_admin"]:
                st.session_state["logado"] = True
                st.rerun()
            else: st.error("Senha incorreta!")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- CONEXÃO GOOGLE SHEETS ---
@st.cache_resource
def conectar():
    cred = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    cred['private_key'] = cred['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(cred)
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- UTILITÁRIOS DE DATA (CRÍTICOS PARA O FILTRO) ---
def normalizar_data_df(df):
    """Identifica a coluna de data e garante que ela seja um objeto de data puro (sem horas) para filtro."""
    possiveis = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    col_alvo = next((c for c in df.columns if c in possiveis), df.columns[0])
    
    # Converte para datetime e remove fuso horário e horas
    df[col_alvo] = pd.to_datetime(df[col_alvo], dayfirst=True, errors='coerce').dt.normalize()
    return df, col_alvo

# --- FUNÇÃO DE GESTÃO ---
def mostrar_tabela_gestao(aba_nome, titulo, link_forms=None, filtrar_hoje=False):
    st.header(titulo)
    if link_forms:
        st.link_button("➕ Realizar Novo Cadastro", link_forms, use_container_width=True)
        st.markdown("---")

    try:
        sh = conectar(); aba = sh.worksheet(aba_nome)
        dados = aba.get_all_records()
        if not dados:
            st.warning("Sem registros."); return
        
        df_full = pd.DataFrame(dados)
        df_full, col_dt = normalizar_data_df(df_full)
        
        col_st = "Status" if "Status" in df_full.columns else "Aprovação"
        if col_st not in df_full.columns: df_full[col_st] = ""
        df_full["Reprovar?"] = df_full[col_st].astype(str).str.contains("Reprovado", case=False, na=False)
        
        cols = ["Reprovar?"] + [c for c in df_full.columns if c not in ["Reprovar?", col_st]]
        df_full = df_full[cols]

        df_disp = df_full.copy()
        if filtrar_hoje:
            hoje = pd.Timestamp(datetime.now().date())
            df_disp = df_disp[df_disp[col_dt] == hoje]
            if df_disp.empty: 
                st.info("Nenhum registro para hoje."); return

        ed = st.data_editor(df_disp, num_rows="dynamic", use_container_width=True, key=f"ed_{aba_nome}")

        if st.button("💾 Salvar Alterações", key=f"bt_{aba_nome}", use_container_width=True):
            df_final = df_full.copy()
            df_final.update(ed)
            df_final[col_st] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df_final = df_final.drop(columns=["Reprovar?"]).astype(str)
            aba.clear(); aba.update([df_final.columns.tolist()] + df_final.values.tolist())
            st.success("Salvo!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- APRESENTAÇÃO (CORREÇÃO DE FILTRO REAL-TIME) ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    if st.button("🔄 Forçar Atualização de Dados"): 
        st.cache_resource.clear()
        st.rerun()
    st.markdown("---")
    
    sh = conectar()
    # Pega o dia de hoje sem as horas para comparação perfeita
    hoje = pd.Timestamp(datetime.now().date())

    # 1. RECADOS
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_recados").get_all_records())
        if not df.empty:
            df, col_dt = normalizar_data_df(df)
            df_hoje = df[(df[col_dt] == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            
            if not df_hoje.empty:
                st.markdown("### 📌 Recados e Avisos")
                for _, r in df_hoje.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-style: italic;">"{r.iloc[3]}"</div><div class="texto-normal" style="font-size: 16px;">Solicitante: {r.iloc[2]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 2. VISITANTES
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_visitante").get_all_records())
        if not df.empty:
            df, col_dt = normalizar_data_df(df)
            df_hoje = df[(df[col_dt] == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            
            if not df_hoje.empty:
                st.markdown("### 🫂 Visitantes")
                for _, r in df_hoje.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-size: 32px;">{r.iloc[2]}</div><div class="texto-normal" style="color: #ffc107; background-color: #0e2433; display: inline-block; padding: 2px 10px; border-radius: 5px;">{r.iloc[3]} | {r.iloc[4]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 3. AUSÊNCIA
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_ausencia").get_all_records())
        if not df.empty:
            df, col_dt = normalizar_data_df(df)
            df_hoje = df[(df[col_dt] == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            
            if not df_hoje.empty:
                st.markdown("### 📉 Ausências Justificadas")
                for _, r in df_hoje.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-size: 30px;">{r.iloc[1]} - {r.iloc[2]}</div><div class="texto-normal" style="font-size: 22px;"><b>Motivo:</b> {r.iloc[3]}</div><div class="texto-normal" style="font-size: 16px; font-style: italic;">Obs: {r.iloc[4]}</div></div>', unsafe_allow_html=True)
    except: pass

    # ORAÇÕES E PARABÉNS (Não filtram por hoje, filtram por aprovação)
    # ... (restante das seções seguindo o mesmo padrão iloc corrigido)

# --- MENU ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True)
    sel = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0)

if sel == "Recados": mostrar_tabela_gestao("cadastro_recados", "📌 Recados", "LINK_RECADO", True)
elif sel == "Visitantes": mostrar_tabela_gestao("cadastro_visitante", "🫂 Visitantes", "LINK_VISITANTE", True)
elif sel == "Ausência": mostrar_tabela_gestao("cadastro_ausencia", "📉 Ausências", "LINK_AUSENCIA", True)
elif sel == "Oração": mostrar_tabela_gestao("cadastro_oracao", "🙏 Orações", "LINK_ORACAO")
elif sel == "Parabenização": mostrar_tabela_gestao("cadastro_parabenizacao", "🎂 Felicitações", "LINK_PARABENS")
elif sel == "Programação": mostrar_tabela_gestao("cadastro_agenda_semanal", "🗓️ Agenda", "LINK_AGENDA")
elif sel == "Apresentação": mostrar_apresentacao()