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
    /* Estilo Original da Barra Lateral e Fundo */
    [data-testid="stSidebar"] { background-color: #0e2433; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stApp { background-color: #f0f2f6; }
    
    /* Botões Amarelos */
    .stButton > button {
        background-color: #ffc107; color: #0e2433;
        border-radius: 10px; border: none; font-weight: bold;
    }
    
    /* Títulos */
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }

    /* --- Estilo para os Cards da Agenda e Apresentação --- */
    .agenda-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 8px solid #0e2433; /* Detalhe azul */
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .agenda-col-c { /* Horário/Destaque */
        font-size: 24px; 
        font-weight: bold; 
        color: #ffc107; /* Amarelo */
        background-color: #0e2433; /* Fundo Azul */
        padding: 5px 10px;
        border-radius: 5px;
        margin-right: 10px;
        min-width: 80px;
        text-align: center;
        display: inline-block;
    }
    .agenda-col-d { /* Evento/Principal */
        font-size: 22px; 
        font-weight: bold; 
        color: #0e2433;
    }
    .agenda-col-a { /* Detalhe extra/Data */
        font-size: 16px; 
        color: #666;
        margin-top: 5px;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- FUNÇÃO DE LOGIN ---
def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h1 style='text-align: center; color: #0e2433;'>🔐 Acesso Restrito</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Átrio - Sistema de Gestão</p>", unsafe_allow_html=True)
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar", use_container_width=True):
            try:
                senha_correta = st.secrets["acesso"]["senha_admin"]
                if senha == senha_correta:
                    st.session_state["logado"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta!")
            except:
                st.error("Erro: Senha não configurada no Secrets.")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar():
    texto_credenciais = st.secrets["gcp_service_account"]["credenciais_json"]
    credenciais = json.loads(texto_credenciais)
    chave_privada = credenciais['private_key'].replace("\\n", "\n")
    credenciais['private_key'] = chave_privada
    gc = gspread.service_account_from_dict(credenciais)
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- UTILITÁRIOS ---
def limpar_hora(valor):
    valor = str(valor).strip()
    if " " in valor:
        try:
            parte_hora = valor.split(" ")[-1]
            if ":" in parte_hora: return parte_hora[:5]
        except: pass
    return "⏰"

def converter_coluna_data(df):
    possiveis = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    coluna_data = next((c for c in df.columns if c in possiveis), df.columns[0])
    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    return df, coluna_data

def filtrar_proxima_semana(df):
    coluna_data = next((c for c in df.columns if "Data" in c and "Carimbo" not in c), df.columns[1])
    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[coluna_data])
    hoje = datetime.now().date()
    ini = hoje + timedelta(days=(0 - hoje.weekday() + 7) % 7)
    fim = ini + timedelta(days=6)
    df_sem = df[(df[coluna_data].dt.date >= ini) & (df[coluna_data].dt.date <= fim)].sort_values(by=coluna_data)
    return df_sem, coluna_data

# --- FUNÇÃO DE GESTÃO ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None, filtrar_hoje=False):
    st.header(f"{titulo_na_tela}")
    try:
        sh = conectar()
        aba = sh.worksheet(nome_aba_sheets)
        dados = aba.get_all_records()
        if not dados:
            st.warning("Aba vazia.")
            if link_forms: st.link_button("➕ Novo Cadastro", link_forms)
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

        st.info("ℹ️ Novos itens nascem Aprovados. Marque 'Reprovar?' e salve para ocultar.")
        df_editado = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, key=f"ed_{nome_aba_sheets}",
                                    column_config={"Reprovar?": st.column_config.CheckboxColumn("Reprovar?", width="small")})

        if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
            df_final = df_full.copy()
            df_final.update(df_editado)
            df_final[col_status] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df_final = df_final.drop(columns=["Reprovar?"]).astype(str)
            aba.clear()
            aba.update([df_final.columns.tolist()] + df_final.values.tolist())
            st.success("Atualizado!")
            time.sleep(1)
            st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- GESTÃO PROGRAMAÇÃO ---
def gerenciar_programacao():
    st.header("🗓️ Programação da Semana")
    sh = conectar()
    aba = sh.worksheet("cadastro_agenda_semanal")
    dados = aba.get_all_records()
    if not dados: return
    df = pd.DataFrame(dados)
    
    with st.expander("✏️ Editar Agenda (Tabela Completa)"):
        col_st = "Status" if "Status" in df.columns else "Aprovação"
        if col_st not in df.columns: df[col_st] = ""
        df["Reprovar?"] = df[col_st].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df.columns if c not in ["Reprovar?", col_st]]
        df_edit = st.data_editor(df[cols], num_rows="dynamic", use_container_width=True, key="ed_agenda")
        if st.button("💾 Salvar Agenda"):
            df_fin = df_edit.copy()
            df_fin[col_st] = df_fin["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            df_fin = df_fin.drop(columns=["Reprovar?"]).astype(str)
            aba.clear()
            aba.update([df_fin.columns.tolist()] + df_fin.values.tolist())
            st.success("Salvo!")
            time.sleep(1); st.rerun()

# --- FUNÇÃO APRESENTAÇÃO (ATUALIZADA) ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    st.markdown(f"**Data:** {datetime.now().strftime('%d/%m/%Y')}")
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Atualizar Lista"):
            st.cache_resource.clear()
            st.rerun()
    st.markdown("---")
    
    sh = conectar()
    hoje = datetime.now().date()

    # --- 1. RECADOS ---
    try:
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df, col_data = converter_coluna_data(df)
            df = df[(df[col_data].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("""<div style='text-align: center; background-color: #0e2433; color: #ffc107; padding: 10px; border-radius: 10px; margin-bottom: 20px; font-size: 20px; font-weight: bold;'>👋 "Cumprimento a igreja com a paz do Senhor!"</div>""", unsafe_allow_html=True)
                st.markdown("### 📌 Recados e Avisos")
                for _, row in df.iterrows():
                    st.markdown(f"""
                    <div class="agenda-card">
                        <div style="font-size: 16px; color: #666;">Pede o recado: {row.get('Quem pede o recado', '')}</div>
                        <div class="agenda-col-d" style="font-size: 24px; color: #0e2433; margin-top:5px;">{row.get('Qual o recado', '')}</div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 2. VISITANTES ---
    try:
        aba = sh.worksheet("cadastro_visitante")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df, col_data = converter_coluna_data(df)
            df = df[(df[col_data].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("### 🫂 Visitantes")
                for _, row in df.iterrows():
                    st.markdown(f"""
                    <div class="agenda-card">
                        <div class="agenda-col-d" style="font-size: 24px;">{row.get('Nome do visitante', '')}</div>
                        <div style="color: #555;">Convidado por: {row.get('Quem convidou', '')} | Igreja: {row.get('Algum ministério/denominação', '')}</div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 3. AUSÊNCIA ---
    try:
        aba = sh.worksheet("cadastro_ausencia")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df, col_data = converter_coluna_data(df)
            df = df[(df[col_data].dt.date == hoje) & (~df["Aprovação"].astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("### 📉 Ausências Justificadas")
                for _, row in df.iterrows():
                    st.markdown(f"""
                    <div class="agenda-card">
                        <div class="agenda-col-d" style="font-size: 24px;">{row.get('Nome', '')} - <span style="color: #ffc107;">{row.get('Cargo', '')}</span></div>
                        <div style="color: #555;"><b>Motivo:</b> {row.get('Motivo', '')} <br> <i>Obs: {row.get('Observação', '')}</i></div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 4. ORAÇÃO ---
    try:
        aba = sh.worksheet("cadastro_oracao")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            if not df.empty:
                st.markdown("### 🙏 Pedidos de Oração")
                for _, row in df.iterrows():
                    st.markdown(f"""
                    <div class="agenda-card" style="border-left: 8px solid #ffc107;">
                        <div class="agenda-col-d" style="font-size: 24px; color: #0e2433;">{row.get('Oração destinada a', '')}</div>
                        <div style="color: #555;"><b>Motivo:</b> {row.get('Motivo da oração', '')} | <i>{row.get('Observação', '')}</i></div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 5. PARABENIZAÇÃO (AGRUPADO) ---
    try:
        aba = sh.worksheet("cadastro_parabenizacao")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", na=False)]
            if not df.empty:
                st.markdown("### 🎂 Felicitações")
                tipos = df["Tipo da felicitação"].unique()
                for tipo in tipos:
                    st.subheader(f"✨ {tipo}")
                    df_tipo = df[df["Tipo da felicitação"] == tipo]
                    for _, row in df_tipo.iterrows():
                        st.markdown(f"""
                        <div class="agenda-card">
                            <div class="agenda-col-d" style="font-size: 24px;">{row.get('Destinado a quem?', '')}</div>
                            <div style="color: #555;">{row.get('Quantos anos / Observação', '')}</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 6. PROGRAMAÇÃO SEMANAL ---
    try:
        aba = sh.worksheet("cadastro_agenda_semanal")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df_semana, col_data = filtrar_proxima_semana(df)
            if not df_semana.empty:
                st.markdown("### 🗓️ Programação da Semana")
                dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
                for i, nome_dia in enumerate(dias_nomes):
                    df_dia = df_semana[df_semana[col_data].dt.weekday == i]
                    if not df_dia.empty:
                        st.markdown(f"#### {nome_dia} ({df_dia.iloc[0][col_data].strftime('%d/%m')})")
                        for _, row in df_dia.iterrows():
                            val_hora = limpar_hora(row.iloc[1])
                            val_desc = row.iloc[2] if len(row) > 2 else ""
                            st.markdown(f"""
                            <div class="agenda-card">
                                <span class="agenda-col-c">{val_hora}</span>
                                <span class="agenda-col-d">{val_desc}</span>
                            </div>""", unsafe_allow_html=True)
    except: pass

# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    if st.button("🚪 Sair / Logout"):
        st.session_state["logado"] = False
        st.rerun()
    st.markdown("---")
    selected = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={
            "container": {"background-color": "#0e2433"},
            "icon": {"color": "orange", "font-size": "20px"},
            "nav-link": {"color": "white", "font-size": "16px", "text-align": "left", "margin": "0px"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"},
        })

# --- ROTEAMENTO ---
if selected == "Recados":
    mostrar_tabela_gestao("cadastro_recados", "📌 Recados do Dia", filtrar_hoje=True)
elif selected == "Visitantes":
    mostrar_tabela_gestao("cadastro_visitante", "Gestão de Visitantes (Dia)", filtrar_hoje=True)
elif selected == "Ausência":
    mostrar_tabela_gestao("cadastro_ausencia", "Justificativas de Ausência (Dia)", filtrar_hoje=True)
elif selected == "Oração":
    mostrar_tabela_gestao("cadastro_oracao", "Gestão de Orações") 
elif selected == "Parabenização":
    mostrar_tabela_gestao("cadastro_parabenizacao", "Parabenizações")
elif selected == "Programação":
    gerenciar_programacao()
elif selected == "Apresentação":
    mostrar_apresentacao()