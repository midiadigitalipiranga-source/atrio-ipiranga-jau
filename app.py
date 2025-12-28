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

    /* --- ESTILO DOS CARDS --- */
    .info-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 10px solid #0e2433;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Texto Principal (Destaque) */
    .card-main-text {
        font-size: 28px; 
        font-weight: 800; 
        color: #0e2433;
        line-height: 1.2;
        margin-bottom: 5px;
    }
    
    /* Texto Secundário (Normal) */
    .card-sub-text {
        font-size: 18px; 
        color: #555;
        font-weight: 500;
    }

    /* Destaque de Hora/Data (Amarelo) */
    .card-highlight {
        font-size: 20px; 
        font-weight: bold; 
        color: #0e2433; 
        background-color: #ffc107; 
        padding: 5px 12px;
        border-radius: 6px;
        display: inline-block;
        margin-bottom: 8px;
    }
    
    /* Recados Especiais */
    .recado-quem {
        font-size: 16px;
        color: #666;
        text-transform: uppercase;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .recado-conteudo {
        font-size: 24px;
        color: #0e2433;
        font-style: italic;
        border-left: 4px solid #ffc107;
        padding-left: 15px;
    }
    
    /* Título de Agrupamento (Parabéns) */
    .group-header {
        font-size: 22px;
        color: #0e2433;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 2px solid #ddd;
        padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state["logado"] = False

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
            except: st.error("Erro no Secrets.")

if not st.session_state["logado"]: tela_login(); st.stop()

# --- CONEXÃO ---
@st.cache_resource
def conectar():
    cred = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    cred['private_key'] = cred['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(cred)
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- UTILITÁRIOS ---
def limpar_hora(valor):
    v = str(valor).strip()
    if " " in v: return v.split(" ")[-1][:5]
    return "⏰"

def safe_get(row, col_name, default_index=None):
    """Tenta pegar pelo nome da coluna, se falhar tenta pelo índice"""
    if col_name in row:
        return str(row[col_name])
    elif default_index is not None and len(row) > default_index:
        return str(row.iloc[default_index])
    return ""

def converter_coluna_data(df):
    col = next((c for c in df.columns if c in ["Carimbo de data/hora", "Timestamp", "Data", "Date"]), df.columns[0])
    df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
    return df, col

# --- GESTÃO PADRÃO ---
def mostrar_tabela_gestao(nome_aba, titulo, link, filtrar_hoje=False):
    st.header(titulo)
    try:
        sh = conectar(); aba = sh.worksheet(nome_aba)
        d = aba.get_all_records()
        if not d: st.warning("Vazio."); st.link_button("➕ Novo", link) if link else None; return
        
        df = pd.DataFrame(d)
        col_status = "Status" if "Status" in df.columns else "Aprovação"
        if col_status not in df.columns: df[col_status] = ""
        
        # Checkbox Reprovar
        df["Reprovar?"] = df[col_status].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df.columns if c not in ["Reprovar?", col_status]]
        df = df[cols]
        
        df_display = df.copy()
        if filtrar_hoje:
            df_display, c_data = converter_coluna_data(df_display)
            df_display = df_display[df_display[c_data].dt.date == datetime.now().date()]
            if df_display.empty: st.info("Nada para hoje.")

        st.info("ℹ️ Novos itens nascem Aprovados. Marque 'Reprovar?' para ocultar.")
        edited = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, key=f"ed_{nome_aba}",
            column_config={"Reprovar?": st.column_config.CheckboxColumn("Reprovar?", width="small")})

        if not edited.empty or not filtrar_hoje:
            col1, col2 = st.columns([1,4])
            with col1:
                if st.button("💾 Salvar", key=f"bt_{nome_aba}"):
                    df_final = df.copy(); df_final.update(edited)
                    df_final[col_status] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
                    df_final.drop(columns=["Reprovar?"], inplace=True)
                    aba.clear(); aba.update([df_final.columns.tolist()] + df_final.astype(str).values.tolist())
                    st.success("Salvo!"); time.sleep(1); st.rerun()
            with col2: st.link_button("➕ Novo", link) if link else None
    except Exception as e: st.error(f"Erro: {e}")

# --- GESTÃO PROGRAMAÇÃO ---
def gerenciar_programacao():
    st.header("🗓️ Programação (Segunda a Domingo)")
    sh = conectar(); aba = sh.worksheet("cadastro_agenda_semanal")
    d = aba.get_all_records(); link = "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform?usp=publish-editor"
    if not d: st.warning("Vazio."); st.link_button("➕ Novo", link); return

    df = pd.DataFrame(d)
    # Filtro Semana
    c_data = next((c for c in df.columns if "Data" in c and "Carimbo" not in c), df.columns[1])
    df[c_data] = pd.to_datetime(df[c_data], dayfirst=True, errors='coerce')
    hoje = datetime.now().date()
    ini = hoje + timedelta(days=(0-hoje.weekday()+7)%7)
    df_sem = df[(df[c_data].dt.date >= ini) & (df[c_data].dt.date <= ini+timedelta(days=6))].sort_values(c_data)
    
    # Visualização
    st.markdown("### 👁️ Visualização")
    if "Aprovação" in df_sem.columns: df_sem = df_sem[~df_sem["Aprovação"].str.contains("Reprovado", na=False)]
    
    if df_sem.empty: st.info("Sem eventos aprovados para a próxima semana.")
    else:
        for i, dia in enumerate(["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]):
            df_d = df_sem[df_sem[c_data].dt.weekday == i]
            if not df_d.empty:
                st.markdown(f"#### {dia} ({df_d.iloc[0][c_data].strftime('%d/%m')})")
                for _, r in df_d.iterrows():
                    hora = limpar_hora(r.iloc[1])
                    desc = r.iloc[2] if len(r)>2 else "Evento"
                    st.markdown(f"""<div class="agenda-card"><span class="agenda-col-c">{hora}</span><span class="agenda-col-d">{desc}</span></div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    # Edição
    with st.expander("✏️ Editar Agenda"):
        col_st = "Status" if "Status" in df.columns else "Aprovação"
        if col_st not in df.columns: df[col_st] = ""
        df["Reprovar?"] = df[col_st].str.contains("Reprovado", na=False)
        cols = ["Reprovar?"] + [c for c in df.columns if c not in ["Reprovar?", col_st]]
        edited = st.data_editor(df[cols], num_rows="dynamic", key="ed_ag", column_config={"Reprovar?": st.column_config.CheckboxColumn(width="small")})
        if st.button("💾 Salvar Agenda"):
            fin = edited.copy()
            fin[col_st] = fin["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
            fin.drop(columns=["Reprovar?"], inplace=True)
            aba.clear(); aba.update([fin.columns.tolist()] + fin.astype(str).values.tolist())
            st.success("Salvo!"); time.sleep(1); st.rerun()

# --- APRESENTAÇÃO PERSONALIZADA ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    st.markdown(f"**Data:** {datetime.now().strftime('%d/%m/%Y')}")
    if st.button("🔄 Atualizar"): st.cache_resource.clear(); st.rerun()
    st.markdown("---")
    
    sh = conectar()
    hoje = datetime.now().date()

    # 1. RECADOS (Quem pede normal, Recado destaque)
    try:
        aba = sh.worksheet("cadastro_recados"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            df, cd = converter_coluna_data(df)
            df = df[(df[cd].dt.date == hoje) & (~df.get("Aprovação", "").astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("""<div style='text-align: center; background-color: #0e2433; color: #ffc107; padding: 10px; border-radius: 10px; margin-bottom: 20px; font-size: 20px; font-weight: bold;'>👋 "Cumprimento a igreja com a paz do Senhor!"</div>""", unsafe_allow_html=True)
                st.markdown("### 📌 Recados e Avisos")
                for _, row in df.iterrows():
                    # Colunas Esperadas: "Quem pede o recado", "Qual o recado"
                    quem = safe_get(row, "Quem pede o recado", 1) # Tenta nome ou index 1
                    recado = safe_get(row, "Qual o recado", 2)    # Tenta nome ou index 2
                    
                    st.markdown(f"""
                    <div class="info-card">
                        <div class="recado-quem">De: {quem}</div>
                        <div class="recado-conteudo">"{recado}"</div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except Exception as e: pass

    # 2. AUSÊNCIA (Nome e Cargo destaque, Motivo e Obs normal)
    try:
        aba = sh.worksheet("cadastro_ausencia"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            df, cd = converter_coluna_data(df)
            df = df[(df[cd].dt.date == hoje) & (~df.get("Aprovação", "").astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("### 📉 Ausências Justificadas")
                for _, row in df.iterrows():
                    nome = safe_get(row, "Nome", 1)
                    cargo = safe_get(row, "Cargo", 2)
                    motivo = safe_get(row, "Motivo", 3)
                    obs = safe_get(row, "Observação", 4)
                    
                    st.markdown(f"""
                    <div class="info-card">
                        <div class="card-main-text">{nome} <span style="font-size: 0.7em; color: #ffc107;">| {cargo}</span></div>
                        <div class="card-sub-text"><b>Motivo:</b> {motivo} <br> <i>{obs}</i></div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # 3. PROGRAMAÇÃO (Lógica da Semana)
    try:
        aba = sh.worksheet("cadastro_agenda_semanal"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            c_data = next((c for c in df.columns if "Data" in c and "Carimbo" not in c), df.columns[1])
            df[c_data] = pd.to_datetime(df[c_data], dayfirst=True, errors='coerce')
            df = df.dropna(subset=[c_data])
            ini = hoje + timedelta(days=(0-hoje.weekday()+7)%7)
            df = df[(df[c_data].dt.date >= ini) & (df[c_data].dt.date <= ini+timedelta(days=6))].sort_values(c_data)
            if "Aprovação" in df.columns: df = df[~df["Aprovação"].str.contains("Reprovado", na=False)]
            
            if not df.empty:
                st.markdown("### 🗓️ Programação da Semana")
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Fiquem atentos aos nossos próximos eventos:</div>", unsafe_allow_html=True)
                for i, dia in enumerate(["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]):
                    df_d = df[df[c_data].dt.weekday == i]
                    if not df_d.empty:
                        st.markdown(f"#### {dia} ({df_d.iloc[0][c_data].strftime('%d/%m')})")
                        for _, r in df_d.iterrows():
                            # 3 Colunas: Carimbo, Data, Descrição
                            hora = limpar_hora(r.iloc[1]) # Tenta tirar hora da data
                            desc = r.iloc[2] if len(r)>2 else "Evento"
                            st.markdown(f"""<div class="agenda-card"><span class="agenda-col-c">{hora}</span><span class="agenda-col-d">{desc}</span></div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # 4. PARABENIZAÇÃO (Agrupado por Tipo)
    try:
        aba = sh.worksheet("cadastro_parabenizacao"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            if "Aprovação" in df.columns: df = df[~df["Aprovação"].str.contains("Reprovado", na=False)]
            
            if not df.empty:
                st.markdown("### 🎂 Felicitações")
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Desejamos muitas felicidades e as ricas bênçãos do céu!</div>", unsafe_allow_html=True)
                
                # Agrupamento
                col_tipo = "Tipo da felicitação" if "Tipo da felicitação" in df.columns else df.columns[1]
                if col_tipo in df.columns:
                    grupos = df.groupby(col_tipo)
                    for tipo, grupo in grupos:
                        st.markdown(f"<div class='group-header'>{tipo}</div>", unsafe_allow_html=True)
                        for _, row in grupo.iterrows():
                            destinado = safe_get(row, "Destinado a quem?", 2)
                            obs = safe_get(row, "Quantos anos / Observação", 3)
                            st.markdown(f"""
                            <div class="info-card">
                                <div class="card-main-text">{destinado}</div>
                                <div class="card-sub-text">{obs}</div>
                            </div>""", unsafe_allow_html=True)
                else:
                    # Se não achar a coluna de tipo, mostra lista simples
                    for _, row in df.iterrows():
                        destinado = row.iloc[2] if len(row)>2 else ""
                        st.markdown(f"<div class='info-card'><div class='card-main-text'>{destinado}</div></div>", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # 5. VISITANTES (Nome destaque, resto normal)
    try:
        aba = sh.worksheet("cadastro_visitante"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            df, cd = converter_coluna_data(df)
            df = df[(df[cd].dt.date == hoje) & (~df.get("Aprovação", "").astype(str).str.contains("Reprovado", na=False))]
            if not df.empty:
                st.markdown("### 🫂 Visitantes")
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Sejam muito bem-vindos à casa do Senhor!</div>", unsafe_allow_html=True)
                for _, row in df.iterrows():
                    nome = safe_get(row, "Nome do visitante", 1)
                    convidou = safe_get(row, "Quem convidou", 2)
                    ministerio = safe_get(row, "Algum ministério/denominação", 3)
                    
                    st.markdown(f"""
                    <div class="info-card">
                        <div class="card-main-text">{nome}</div>
                        <div class="card-sub-text">Convite de: {convidou} | Igreja: {ministerio}</div>
                    </div>""", unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # 6. ORAÇÃO (Destino destaque, Motivo normal)
    try:
        aba = sh.worksheet("cadastro_oracao"); df = pd.DataFrame(aba.get_all_records())
        if not df.empty:
            if "Aprovação" in df.columns: df = df[~df["Aprovação"].str.contains("Reprovado", na=False)]
            if not df.empty:
                st.markdown("### 🙏 Pedidos de Oração")
                for _, row in df.iterrows():
                    destino = safe_get(row, "Oração destinada a", 1)
                    motivo = safe_get(row, "Motivo da oração", 2)
                    obs = safe_get(row, "Observação", 3)
                    
                    st.markdown(f"""
                    <div class="info-card">
                        <div class="card-main-text">{destino}</div>
                        <div class="card-sub-text"><b>Motivo:</b> {motivo} <br> <i>{obs}</i></div>
                    </div>""", unsafe_allow_html=True)
    except: pass


# --- MENU ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    if st.button("🚪 Sair"): st.session_state["logado"] = False; st.rerun()
    st.markdown("---")
    selected = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={"container": {"background-color": "#0e2433"}, "nav-link": {"color": "white"}, "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}})

# --- ROTAS ---
if selected == "Recados":
    mostrar_tabela_gestao("cadastro_recados", "📌 Recados do Dia", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform?usp=publish-editor", filtrar_hoje=True)
elif selected == "Visitantes":
    mostrar_tabela_gestao("cadastro_visitante", "Gestão de Visitantes (Dia)", "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform?usp=header", filtrar_hoje=True)
elif selected == "Ausência":
    mostrar_tabela_gestao("cadastro_ausencia", "Justificativas de Ausência (Dia)", "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform?usp=header", filtrar_hoje=True)
elif selected == "Oração":
    mostrar_tabela_gestao("cadastro_oracao", "Gestão de Orações", "https://docs.google.com/forms/d/e/1FAIpQLSe8W9x1Q9AwlSXytO3NDFvi2SgMKpfC6ICTVhMVH92S48KyyQ/viewform?usp=publish-editor") 
elif selected == "Parabenização":
    mostrar_tabela_gestao("cadastro_parabenizacao", "Parabenizações", "https://docs.google.com/forms/d/e/1FAIpQLSdI4ConKeN9T1iKFHTgtO89f71vMXdjrbmdbb20zGK0nMUDtw/viewform?usp=publish-editor")
elif selected == "Programação":
    gerenciar_programacao()
elif selected == "Apresentação":
    mostrar_apresentacao()