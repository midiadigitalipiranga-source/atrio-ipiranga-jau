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
    .agenda-col-c { font-size: 24px; font-weight: bold; color: #ffc107; background-color: #0e2433; padding: 5px 10px; border-radius: 5px; display: inline-block; }
    .agenda-col-d { font-size: 22px; font-weight: bold; color: #0e2433; }
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

# --- UTILITÁRIOS DE DATA (CORRIGIDOS) ---
def converter_coluna_data(df):
    """Detecta e converte colunas de data para o formato datetime do Python de forma robusta."""
    possiveis = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    col = next((c for c in df.columns if c in possiveis), df.columns[0])
    
    # Converte forçando o formato de data e removendo informações de fuso horário para comparação limpa
    df[col] = pd.to_datetime(df[col], errors='coerce').dt.tz_localize(None)
    return df, col

def limpar_hora(valor):
    v = str(valor).strip()
    if " " in v:
        try:
            h = v.split(" ")[-1]
            if ":" in h: return h[:5]
        except: pass
    return "⏰"

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
            st.warning("Sem registros para exibir."); return
        
        df_full = pd.DataFrame(dados)
        df_full, c_dt = converter_coluna_data(df_full) # Aplica conversão robusta
        
        col_st = "Status" if "Status" in df_full.columns else "Aprovação"
        if col_st not in df_full.columns: df_full[col_st] = ""
        df_full["Reprovar?"] = df_full[col_st].astype(str).str.contains("Reprovado", case=False, na=False)
        
        cols = ["Reprovar?"] + [c for c in df_full.columns if c not in ["Reprovar?", col_st]]
        df_full = df_full[cols]

        df_disp = df_full.copy()
        if filtrar_hoje:
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_disp = df_disp[df_disp[c_dt].dt.normalize() == hoje]
            if df_disp.empty: 
                st.info("Nenhum registro para hoje.")
                return

        # Formata a visualização da data para o padrão BR na tabela de gestão
        df_edit_view = df_disp.copy()
        df_edit_view[c_dt] = df_edit_view[c_dt].dt.strftime('%d/%m/%Y %H:%M:%S')

        ed = st.data_editor(df_edit_view, num_rows="dynamic", use_container_width=True, key=f"ed_{aba_nome}")

        if st.button("💾 Salvar Alterações", key=f"bt_{aba_nome}", use_container_width=True):
            df_final = df_full.copy()
            # Atualiza apenas a coluna de reprovação baseada no editor
            df_final.loc[df_disp.index, col_st] = ed["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df_final = df_final.drop(columns=["Reprovar?"]).astype(str)
            aba.clear(); aba.update([df_final.columns.tolist()] + df_final.values.tolist())
            st.success("Salvo!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- APRESENTAÇÃO CORRIGIDA ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    if st.button("🔄 Atualizar Lista"): st.cache_resource.clear(); st.rerun()
    st.markdown("---")
    
    sh = conectar()
    # Pega a data de hoje "limpa" (sem horas) para comparação
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. RECADOS
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_recados").get_all_records())
        if not df.empty:
            df, c_dt = converter_coluna_data(df)
            # Normaliza a data da planilha para comparar apenas Dia/Mês/Ano
            df = df[(df[c_dt].dt.normalize() == hoje)]
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            
            if not df.empty:
                st.markdown("### 📌 Recados e Avisos")
                for _, r in df.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-style: italic;">"{r.iloc[3]}"</div><div class="texto-normal" style="font-size: 16px;">Solicitante: {r.iloc[2]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 2. VISITANTES
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_visitante").get_all_records())
        if not df.empty:
            df, c_dt = converter_coluna_data(df)
            df = df[(df[c_dt].dt.normalize() == hoje)]
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            
            if not df.empty:
                st.markdown("### 🫂 Visitantes")
                for _, r in df.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-size: 32px;">{r.iloc[2]}</div><div class="texto-normal" style="color: #ffc107; background-color: #0e2433; display: inline-block; padding: 2px 10px; border-radius: 5px;">{r.iloc[3]} | {r.iloc[4]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 3. AUSÊNCIA
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_ausencia").get_all_records())
        if not df.empty:
            df, c_dt = converter_coluna_data(df)
            df = df[(df[c_dt].dt.normalize() == hoje)]
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            
            if not df.empty:
                st.markdown("### 📉 Ausências Justificadas")
                for _, r in df.iterrows():
                    st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-size: 30px;">{r.iloc[1]} - {r.iloc[2]}</div><div class="texto-normal" style="font-size: 22px;"><b>Motivo:</b> {r.iloc[3]}</div><div class="texto-normal" style="font-size: 16px; font-style: italic;">Obs: {r.iloc[4]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 4. ORAÇÃO (Não depende de data de hoje)
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_oracao").get_all_records())
        if not df.empty:
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            if not df.empty:
                st.markdown("### 🙏 Pedidos de Oração")
                for mot in df.iloc[:, 2].unique():
                    st.markdown(f"<h4 style='color: #0e2433; border-bottom: 2px solid #ffc107;'>🎯 Motivo: {mot}</h4>", unsafe_allow_html=True)
                    df_mot = df[df.iloc[:, 2] == mot]
                    for _, r in df_mot.iterrows():
                        st.markdown(f'<div class="agenda-card" style="border-left: 8px solid #ffc107;"><div class="texto-destaque">{r.iloc[1]}</div><div class="texto-normal">Motivo: {mot}</div><div style="font-size: 14px; color: #666;">Obs: {r.iloc[3]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 5. PARABENIZAÇÃO
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_parabenizacao").get_all_records())
        if not df.empty:
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            df = df.sort_values(by=df.columns[0])
            if not df.empty:
                st.markdown("### 🎂 Felicitações")
                for tip in df.iloc[:, 2].unique():
                    st.markdown(f"#### ✨ {tip}")
                    df_tip = df[df.iloc[:, 2] == tip]
                    for _, r in df_tip.iterrows():
                        st.markdown(f'<div class="agenda-card"><div class="texto-destaque" style="font-size: 30px;">{r.iloc[1]}</div><div class="texto-normal">{tip} — {r.iloc[3]}</div></div>', unsafe_allow_html=True)
    except: pass

    # 6. PROGRAMAÇÃO
    try:
        df = pd.DataFrame(sh.worksheet("cadastro_agenda_semanal").get_all_records())
        df_s, c_dt = filtrar_proxima_semana(df)
        if not df_s.empty:
            st.markdown("### 🗓️ Programação da Semana")
            for i, d in enumerate(["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]):
                df_d = df_s[df_s[c_dt].dt.weekday == i]
                if not df_d.empty:
                    st.markdown(f"#### {d} ({df_d.iloc[0][c_dt].strftime('%d/%m')})")
                    for _, r in df_d.iterrows():
                        st.markdown(f'<div class="agenda-card"><span class="agenda-col-c">{limpar_hora(r.iloc[1])}</span><span class="agenda-col-d">{r.iloc[2]}</span></div>', unsafe_allow_html=True)
    except: pass

# --- MENU E ROTEAMENTO ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True)
    sel = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={"container": {"background-color": "#0e2433"}, "nav-link": {"color": "white"}, "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}})

if sel == "Recados": mostrar_tabela_gestao("cadastro_recados", "📌 Recados", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", True)
elif sel == "Visitantes": mostrar_tabela_gestao("cadastro_visitante", "🫂 Visitantes", "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform", True)
elif sel == "Ausência": mostrar_tabela_gestao("cadastro_ausencia", "📉 Ausências", "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform", True)
elif sel == "Oração": mostrar_tabela_gestao("cadastro_oracao", "🙏 Orações", "https://docs.google.com/forms/d/e/1FAIpQLSe8W9x1Q9AwlSXytO3NDFvi2SgMKpfC6ICTVhMVH92S48KyyQ/viewform")
elif sel == "Parabenização": mostrar_tabela_gestao("cadastro_parabenizacao", "🎂 Felicitações", "https://docs.google.com/forms/d/e/1FAIpQLSdI4ConKeN9T1iKFHTgtO89f71vMXdjrbmdbb20zGK0nMUDtw/viewform")
elif sel == "Programação": mostrar_tabela_gestao("cadastro_agenda_semanal", "🗓️ Agenda", "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform")
elif sel == "Apresentação": mostrar_apresentacao()