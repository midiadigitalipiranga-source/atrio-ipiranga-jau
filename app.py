import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA (TELA CHEIA) ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- CSS PERSONALIZADO ---
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
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO E LOGIN ---
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
                else:
                    st.error("Senha incorreta!")
            except:
                st.error("Erro nas configurações de segurança.")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- CONEXÃO E UTILITÁRIOS ---
@st.cache_resource
def conectar():
    creds = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    creds['private_key'] = creds['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(creds)
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

def limpar_hora(valor):
    valor = str(valor).strip()
    if " " in valor:
        try:
            parte = valor.split(" ")[-1]
            if ":" in parte: return parte[:5]
        except: pass
    return "⏰"

def converter_coluna_data(df):
    possiveis = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    col_data = next((c for c in df.columns if c in possiveis), df.columns[0])
    df[col_data] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
    return df, col_data

def filtrar_proxima_semana(df):
    col_data = next((c for c in df.columns if "Data" in c and "Carimbo" not in c), df.columns[1])
    df[col_data] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[col_data])
    hoje = datetime.now().date()
    ini = hoje + timedelta(days=(0 - hoje.weekday() + 7) % 7)
    df_sem = df[(df[col_data].dt.date >= ini) & (df[col_data].dt.date <= ini + timedelta(days=6))].sort_values(by=col_data)
    return df_sem, col_data

# --- GESTÃO ---
def mostrar_tabela_gestao(aba_nome, titulo, link=None, filtrar_hoje=False):
    st.header(titulo)
    try:
        sh = conectar()
        aba = sh.worksheet(aba_nome)
        dados = aba.get_all_records()
        if not dados:
            st.warning("Nenhum registro encontrado.")
            return
        
        df_full = pd.DataFrame(dados)
        col_status = "Status" if "Status" in df_full.columns else "Aprovação"
        if col_status not in df_full.columns: df_full[col_status] = ""

        df_full["Reprovar?"] = df_full[col_status].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df_full.columns if c not in ["Reprovar?", col_status]]
        df_full = df_full[cols]

        df_display = df_full.copy()
        if filtrar_hoje:
            df_display, col_data_nome = converter_coluna_data(df_display)
            df_display = df_display[df_display[col_data_nome].dt.date == datetime.now().date()]

        df_editado = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, key=f"ed_{aba_nome}",
                                    column_config={"Reprovar?": st.column_config.CheckboxColumn("Reprovar?", width="small")})

        if st.button("💾 Salvar Alterações", key=f"btn_{aba_nome}"):
            df_final = df_full.copy()
            df_final.update(df_editado)
            df_final[col_status] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df_final = df_final.drop(columns=["Reprovar?"]).astype(str)
            aba.clear()
            aba.update([df_final.columns.tolist()] + df_final.values.tolist())
            st.success("Dados salvos com sucesso!")
            time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro na gestão: {e}")

# --- APRESENTAÇÃO ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    st.markdown(f"**Data:** {datetime.now().strftime('%d/%m/%Y')}")
    if st.button("🔄 Atualizar Dados"):
        st.cache_resource.clear()
        st.rerun()
    st.markdown("---")
    
    sh = conectar()
    hoje = datetime.now().date()

    # 1. RECADOS
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_recados").get_all_records())
        df, col_d = converter_coluna_data(df)
        df = df[(df[col_d].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
        if not df.empty:
            st.markdown("### 📌 Recados e Avisos")
            for _, r in df.iterrows():
                st.markdown(f'<div class="agenda-card"><div style="font-size: 16px; color: #666;">Pede o recado: {r.get("Quem pede o recado", "")}</div><div class="agenda-col-d" style="font-size: 24px; color: #0e2433; margin-top:5px;">{r.get("Qual o recado", "")}</div></div>', unsafe_allow_html=True)
    except: pass

    # 2. VISITANTES
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_visitante").get_all_records())
        df, col_d = converter_coluna_data(df)
        df = df[(df[col_d].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
        if not df.empty:
            st.markdown("### 🫂 Visitantes")
            for _, r in df.iterrows():
                st.markdown(f'<div class="agenda-card"><div class="agenda-col-d" style="font-size: 24px;">{r.get("Nome do visitante", "")}</div><div style="color: #555;">Convidado por: {r.get("Quem convidou", "")} | Igreja: {r.get("Algum ministério/denominação", "")}</div></div>', unsafe_allow_html=True)
    except: pass

    # 3. AUSÊNCIA
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_ausencia").get_all_records())
        df, col_d = converter_coluna_data(df)
        df = df[(df[col_d].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
        if not df.empty:
            st.markdown("### 📉 Ausências Justificadas")
            for _, r in df.iterrows():
                st.markdown(f'<div class="agenda-card"><div class="agenda-col-d" style="font-size: 24px;">{r.get("Nome", "")} - <span style="color: #ffc107;">{r.get("Cargo", "")}</span></div><div style="color: #555;"><b>Motivo:</b> {r.get("Motivo", "")} <br> <i>Obs: {r.get("Observação", "")}</i></div></div>', unsafe_allow_html=True)
    except: pass

    # 4. ORAÇÃO
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_oracao").get_all_records())
        df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
        if not df.empty:
            st.markdown("### 🙏 Pedidos de Oração")
            for _, r in df.iterrows():
                st.markdown(f'<div class="agenda-card" style="border-left: 8px solid #ffc107;"><div class="agenda-col-d" style="font-size: 24px; color: #0e2433;">{r.get("Oração destinada a", "")}</div><div style="color: #555;"><b>Motivo:</b> {r.get("Motivo da oração", "")} | <i>{r.get("Observação", "")}</i></div></div>', unsafe_allow_html=True)
    except: pass

    # 5. PARABENIZAÇÃO
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_parabenizacao").get_all_records())
        df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
        if not df.empty:
            st.markdown("### 🎂 Felicitações")
            for tipo in df["Tipo da felicitação"].unique():
                st.subheader(f"✨ {tipo}")
                for _, r in df[df["Tipo da felicitação"] == tipo].iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="agenda-col-d" style="font-size: 24px;">{r.get("Destinado a quem?", "")}</div><div style="color: #555;">{r.get("Quantos anos / Observação", "")}</div></div>', unsafe_allow_html=True)
    except: pass

# --- MENU E ROTAS ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    selected = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={"container": {"background-color": "#0e2433"}, "nav-link": {"color": "white"}, "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}})

if selected == "Recados": mostrar_tabela_gestao("cadastro_recados", "📌 Gestão de Recados", filtrar_hoje=True)
elif selected == "Visitantes": mostrar_tabela_gestao("cadastro_visitante", "🫂 Gestão de Visitantes", filtrar_hoje=True)
elif selected == "Ausência": mostrar_tabela_gestao("cadastro_ausencia", "📉 Gestão de Ausências", filtrar_hoje=True)
elif selected == "Oração": mostrar_tabela_gestao("cadastro_oracao", "🙏 Gestão de Orações")
elif selected == "Parabenização": mostrar_tabela_gestao("cadastro_parabenizacao", "🎂 Gestão de Felicitações")
elif selected == "Apresentação": mostrar_apresentacao()