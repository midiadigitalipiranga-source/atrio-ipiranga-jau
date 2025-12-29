import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA (TELA CHEIA) ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- CSS PERSONALIZADO (Restaurando o Original) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0e2433; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stApp { background-color: #f0f2f6; }
    
    .stButton > button {
        background-color: #ffc107; color: #0e2433;
        border-radius: 10px; border: none; font-weight: bold;
    }
    
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }

    .agenda-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 8px solid #0e2433;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .agenda-col-c {
        font-size: 24px; 
        font-weight: bold; 
        color: #ffc107;
        background-color: #0e2433;
        padding: 5px 10px;
        border-radius: 5px;
        margin-right: 10px;
        min-width: 80px;
        text-align: center;
        display: inline-block;
    }
    .agenda-col-d {
        font-size: 22px; 
        font-weight: bold; 
        color: #0e2433;
    }
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
        st.markdown("<br><br><h1 style='text-align: center; color: #0e2433;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar", use_container_width=True):
            try:
                if senha == st.secrets["acesso"]["senha_admin"]:
                    st.session_state["logado"] = True
                    st.rerun()
                else: st.error("Senha incorreta!")
            except: st.error("Erro nas configurações.")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- CONEXÃO ---
@st.cache_resource
def conectar():
    cred = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    cred['private_key'] = cred['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(cred)
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- FERRAMENTAS DE DATA ---
def converter_para_data_limpa(df):
    """Garante que a data seja comparável ignorando horas e formatos estranhos."""
    possiveis = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    col = next((c for c in df.columns if c in possiveis), df.columns[0])
    # Converte para data pura (Y-M-D) ignorando as horas do carimbo do Google
    df[col] = pd.to_datetime(df[col], errors='coerce').dt.normalize()
    return df, col

def limpar_hora(valor):
    v = str(valor).strip()
    if " " in v:
        try:
            h = v.split(" ")[-1]
            if ":" in h: return h[:5]
        except: pass
    return "⏰"

# --- GESTÃO ---
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
        df = pd.DataFrame(dados)
        df, col_dt = converter_para_data_limpa(df)
        
        status_col = "Aprovação" if "Aprovação" in df.columns else "Status"
        if status_col not in df.columns: df[status_col] = ""
        
        df["Reprovar?"] = df[status_col].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df.columns if c not in ["Reprovar?", status_col]]
        df = df[cols]

        df_view = df.copy()
        if filtrar_hoje:
            hoje = pd.Timestamp(datetime.now().date())
            df_view = df_view[df_view[col_dt] == hoje]
            if df_view.empty: st.info("Nada para hoje."); return

        ed = st.data_editor(df_view, num_rows="dynamic", use_container_width=True, key=f"ed_{aba_nome}")
        if st.button("💾 Salvar", key=f"bt_{aba_nome}"):
            df.update(ed)
            df[status_col] = df["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df = df.drop(columns=["Reprovar?"]).astype(str)
            aba.clear(); aba.update([df.columns.tolist()] + df.values.tolist())
            st.success("Salvo!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- APRESENTAÇÃO (CORRIGIDA) ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    if st.button("🔄 Atualizar"): st.cache_resource.clear(); st.rerun()
    st.markdown("---")
    sh = conectar(); hoje = pd.Timestamp(datetime.now().date())

    # Lógica repetida para cada seção com o filtro de data normalizado
    secoes = [
        ("cadastro_recados", "📌 Recados", 2, 1),
        ("cadastro_visitante", "🫂 Visitantes", 2, 3),
        ("cadastro_ausencia", "📉 Ausências", 1, 2)
    ]

    for aba, titulo, idx_h1, idx_h2 in secoes:
        try:
            df = pd.DataFrame(sh.worksheet(aba).get_all_records())
            df, c = converter_para_data_limpa(df)
            df = df[(df[c] == hoje) & (~df["Aprovação"].str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown(f"### {titulo}")
                for _, r in df.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque">{r.iloc[idx_h1]}</div><div class="texto-normal">{r.iloc[idx_h2]}</div></div>', unsafe_allow_html=True)
        except: pass

    # --- ORAÇÃO, PARABÉNS E AGENDA ---
    # (Mantidos conforme sua versão funcional anterior)
    try:
        df_p = pd.DataFrame(sh.worksheet("cadastro_parabenizacao").get_all_records())
        df_p = df_p[~df_p["Aprovação"].str.contains("Reprovado", na=False)].sort_values(by=df_p.columns[0])
        if not df_p.empty:
            st.markdown("### 🎂 Felicitações")
            for t in df_p.iloc[:, 2].unique():
                st.markdown(f"#### ✨ {t}")
                for _, r in df_p[df_p.iloc[:, 2] == t].iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque">{r.iloc[1]}</div></div>', unsafe_allow_html=True)
    except: pass

# --- MENU LATERAL (CORES ORIGINAIS) ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True)
    sel = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={
            "container": {"background-color": "#0e2433"},
            "icon": {"color": "#ffc107"},
            "nav-link": {"color": "white"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}
        })

# Roteamento simples
if sel == "Recados": mostrar_tabela_gestao("cadastro_recados", "📌 Recados", "LINK_RECADO", True)
elif sel == "Visitantes": mostrar_tabela_gestao("cadastro_visitante", "🫂 Visitantes", "LINK_VISITANTE", True)
elif sel == "Ausência": mostrar_tabela_gestao("cadastro_ausencia", "📉 Ausências", "LINK_AUSENCIA", True)
elif sel == "Oração": mostrar_tabela_gestao("cadastro_oracao", "🙏 Orações", "LINK_ORACAO")
elif sel == "Parabenização": mostrar_tabela_gestao("cadastro_parabenizacao", "🎂 Felicitações", "LINK_PARABENS")
elif sel == "Programação": mostrar_tabela_gestao("cadastro_agenda_semanal", "🗓️ Agenda", "LINK_AGENDA")
elif sel == "Apresentação": mostrar_apresentacao()