import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO DA PÁGINA (TELA CHEIA) ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- CSS PERSONALIZADO (VISUAL MELHORADO PARA APRESENTAÇÃO) ---
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

    /* --- ESTILO DOS CARDS (AGENDA E GERAL) --- */
    .info-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 10px solid #0e2433; /* Detalhe azul */
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Texto Principal (Nome, Evento) */
    .card-main-text {
        font-size: 26px; 
        font-weight: 800; 
        color: #0e2433;
        line-height: 1.2;
    }
    
    /* Texto Secundário (Detalhes, Motivo) */
    .card-sub-text {
        font-size: 18px; 
        color: #555;
        margin-top: 5px;
    }

    /* Destaque de Hora/Data (Amarelo) */
    .card-highlight {
        font-size: 20px; 
        font-weight: bold; 
        color: #0e2433; /* Texto azul */
        background-color: #ffc107; /* Fundo Amarelo */
        padding: 5px 12px;
        border-radius: 6px;
        display: inline-block;
        margin-bottom: 8px;
    }
    
    /* Texto de Recado (Corpo do texto) */
    .recado-text {
        font-size: 24px;
        font-style: italic;
        color: #333;
        border-left: 4px solid #ddd;
        padding-left: 15px;
        margin-top: 10px;
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

# ==============================================================================
# SISTEMA ÁTRIO (LOGADO)
# ==============================================================================

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar():
    texto_credenciais = st.secrets["gcp_service_account"]["credenciais_json"]
    credenciais = json.loads(texto_credenciais)
    
    chave_privada = credenciais['private_key']
    if "\\n" in chave_privada:
        chave_privada = chave_privada.replace("\\n", "\n")
    credenciais['private_key'] = chave_privada

    gc = gspread.service_account_from_dict(credenciais)
    KEY = "16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I" 
    sh = gc.open_by_key(KEY)
    return sh

# --- FUNÇÃO AUXILIAR: LIMPAR HORA ---
def limpar_hora(valor):
    valor = str(valor).strip()
    if " " in valor:
        try:
            parte_hora = valor.split(" ")[-1]
            if ":" in parte_hora:
                return parte_hora[:5]
        except: pass
    return "⏰"

# --- FUNÇÃO AUXILIAR: FILTRAR SEMANA ---
def filtrar_proxima_semana(df):
    coluna_data = None
    for col in df.columns:
        if "Data" in col and "Carimbo" not in col:
            coluna_data = col
            break
    if not coluna_data:
        for col in df.columns:
            if "Data" in col or "Carimbo" in col:
                coluna_data = col
                break
    
    if not coluna_data:
        return pd.DataFrame(), None

    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[coluna_data])

    hoje = datetime.now().date()
    dias_para_segunda = (0 - hoje.weekday() + 7) % 7
    inicio_semana = hoje + timedelta(days=dias_para_segunda)
    fim_semana = inicio_semana + timedelta(days=6)

    df_semana = df[(df[coluna_data].dt.date >= inicio_semana) & (df[coluna_data].dt.date <= fim_semana)]
    df_semana = df_semana.sort_values(by=coluna_data)
    
    return df_semana, coluna_data

# --- FUNÇÃO AUXILIAR GERAL ---
def converter_coluna_data(df):
    coluna_data = None
    possiveis_nomes = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    for col in df.columns:
        if col in possiveis_nomes:
            coluna_data = col
            break
    if not coluna_data: coluna_data = df.columns[0]
    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    return df, coluna_data

# --- FUNÇÃO DE GESTÃO PADRÃO ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None, filtrar_hoje=False):
    st.header(f"{titulo_na_tela}")
    try:
        sh = conectar()
        try: aba = sh.worksheet(nome_aba_sheets)
        except: st.error(f"Aba '{nome_aba_sheets}' não encontrada!"); return

        dados = aba.get_all_records()
        if not dados:
            st.warning("A aba existe, mas está vazia.")
            if link_forms: st.markdown("---"); st.link_button(f"➕ Novo Cadastro", link_forms); return
        else: df_full = pd.DataFrame(dados)
        
        coluna_status = "Aprovação"
        if "Status" in df_full.columns: coluna_status = "Status"
        elif "Aprovação" not in df_full.columns: df_full["Aprovação"] = ""

        df_full["Reprovar?"] = df_full[coluna_status].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df_full.columns if c != "Reprovar?" and c != coluna_status]
        df_full = df_full[cols]

        df_display = df_full.copy()
        
        if filtrar_hoje:
            df_display, col_data_nome = converter_coluna_data(df_display)
            hoje = datetime.now().date()
            df_display = df_display[df_display[col_data_nome].dt.date == hoje]
            if df_display.empty: st.info(f"Nenhum registro encontrado para HOJE ({hoje.strftime('%d/%m/%Y')}).")

        st.info("ℹ️ Novos itens já nascem Aprovados. Marque a caixa 'Reprovar?' e salve para remover da apresentação.")
        
        df_editado_na_tela = st.data_editor(
            df_display, 
            num_rows="dynamic", 
            use_container_width=True, 
            key=f"editor_{nome_aba_sheets}",
            column_config={
                "Reprovar?": st.column_config.CheckboxColumn("Reprovar?", default=False, width="small"),
                **( {col_data_nome: st.column_config.DateColumn("Data", format="DD/MM/YYYY")} if filtrar_hoje and not df_display.empty else {} )
            }
        )

        if not df_editado_na_tela.empty or not filtrar_hoje:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
                    with st.spinner("Salvando..."):
                        df_final = df_full.copy()
                        df_final.update(df_editado_na_tela)
                        df_final[coluna_status] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
                        df_final = df_final.drop(columns=["Reprovar?"])
                        if filtrar_hoje: df_final = df_final.astype(str)
                        aba.clear()
                        aba.update([df_final.columns.values.tolist()] + df_final.values.tolist())
                        st.success("Atualizado!")
                        time.sleep(1)
                        st.rerun()
            with col2:
                if link_forms: st.link_button(f"➕ Novo Cadastro", link_forms)
        else:
             if link_forms: st.link_button(f"➕ Novo Cadastro", link_forms)
    except Exception as e: st.error(f"Erro: {e}")

# --- FUNÇÃO GESTÃO DA PROGRAMAÇÃO ---
def gerenciar_programacao():
    st.header("🗓️ Programação da Semana (Segunda a Domingo)")
    
    sh = conectar()
    try: aba = sh.worksheet("cadastro_agenda_semanal")
    except: st.error("Aba 'cadastro_agenda_semanal' não encontrada."); return
    
    dados = aba.get_all_records()
    link_forms = "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform?usp=publish-editor"

    if not dados:
        st.warning("Agenda vazia.")
        st.link_button("➕ Novo Evento", link_forms)
        return

    df = pd.DataFrame(dados)
    st.markdown("### 👁️ Visualização da Próxima Semana")
    
    df_semana, col_data_filtro = filtrar_proxima_semana(df.copy())
    
    if "Aprovação" in df_semana.columns:
        df_semana = df_semana[~df_semana["Aprovação"].astype(str).str.contains("Reprovado", case=False, na=False)]
    
    if df_semana.empty:
        st.info("Nenhum evento aprovado para a semana que vem.")
    else:
        dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
        for i, nome_dia in enumerate(dias_nomes):
            df_dia = df_semana[df_semana[col_data_filtro].dt.weekday == i]
            if not df_dia.empty:
                data_str = df_dia.iloc[0][col_data_filtro].strftime('%d/%m')
                st.markdown(f"#### {nome_dia} - {data_str}")
                for _, row in df_dia.iterrows():
                    val_c = limpar_hora(row.iloc[1]) # Tenta hora da coluna data
                    val_desc = row.iloc[2] if len(row) > 2 else "Evento"
                    st.markdown(f"""
                    <div class="info-card">
                        <span class="card-highlight">{val_c}</span>
                        <div class="card-main-text">{val_desc}</div>
                    </div>""", unsafe_allow_html=True)
    st.markdown("---")
    
    with st.expander("✏️ Editar Agenda (Tabela Completa)"):
        st.info("ℹ️ Novos itens já nascem Aprovados. Marque 'Reprovar?' para ocultar.")
        
        coluna_status = "Aprovação"
        if "Status" in df.columns: coluna_status = "Status"
        elif "Aprovação" not in df.columns: df["Aprovação"] = ""
        
        df["Reprovar?"] = df[coluna_status].astype(str).str.contains("Reprovado", case=False, na=False)
        cols = ["Reprovar?"] + [c for c in df.columns if c != "Reprovar?" and c != coluna_status]
        df = df[cols]

        df_editado = st.data_editor(
            df, 
            num_rows="dynamic", 
            use_container_width=True, 
            key="edit_agenda",
            column_config={
                "Reprovar?": st.column_config.CheckboxColumn("Reprovar?", width="small")
            }
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Salvar Agenda"):
                df_final = df_editado.copy()
                df_final[coluna_status] = df_final["Reprovar?"].apply(lambda x: "❌ Reprovado" if x else "✅ Aprovado")
                df_final = df_final.drop(columns=["Reprovar?"])
                df_final = df_final.astype(str)
                aba.clear()
                aba.update([df_final.columns.values.tolist()] + df_final.values.tolist())
                st.success("Salvo!")
                time.sleep(1)
                st.rerun()
        with col2:
            st.link_button("➕ Novo Evento", link_forms)

# --- FUNÇÃO APRESENTAÇÃO (VISUAL NOVO: CARDS) ---
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

    # --- 1. RECADOS ---
    try:
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            df, col_data = converter_coluna_data(df)
            hoje = datetime.now().date()
            df = df[df[col_data].dt.date == hoje]
            
            if "Aprovação" in df.columns: 
                df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", case=False, na=False)]
            
            if not df.empty:
                st.markdown("""<div style='text-align: center; background-color: #0e2433; color: #ffc107; padding: 10px; border-radius: 10px; margin-bottom: 20px; font-size: 20px; font-weight: bold;'>👋 "Cumprimento a igreja com a paz do Senhor!"</div>""", unsafe_allow_html=True)
                st.markdown("### 📌 Recados e Avisos")
                
                # LOOP PARA CRIAR CARDS DE RECADOS
                for _, row in df.iterrows():
                    # Geralmente Coluna 2 é o recado
                    texto_recado = row.iloc[2] if len(row) > 2 else "Sem texto"
                    st.markdown(f"""
                    <div class="info-card">
                        <div class="recado-text">"{texto_recado}"</div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 2. PROGRAMAÇÃO SEMANAL ---
    try:
        aba = sh.worksheet("cadastro_agenda_semanal")
        dados = aba.get_all_records()
        if dados:
            df = pd.DataFrame(dados)
            if "Aprovação" in df.columns: 
                df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", case=False, na=False)]
            
            df_semana, col_data = filtrar_proxima_semana(df)
            
            if not df_semana.empty:
                st.markdown("### 🗓️ Programação da Semana")
                
                dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
                
                for i, nome_dia in enumerate(dias_nomes):
                    df_dia = df_semana[df_semana[col_data].dt.weekday == i]
                    if not df_dia.empty:
                        data_str = df_dia.iloc[0][col_data].strftime('%d/%m')
                        st.markdown(f"#### {nome_dia} ({data_str})")
                        
                        for _, row in df_dia.iterrows():
                            val_c = limpar_hora(row.iloc[1])
                            val_desc = row.iloc[2] if len(row) > 2 else "Evento"
                            
                            st.markdown(f"""
                            <div class="info-card">
                                <span class="card-highlight">{val_c}</span>
                                <div class="card-main-text">{val_desc}</div>
                            </div>
                            """, unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 3. OUTROS (VISITANTES, PARABENS, ETC) - AGORA COM CARDS ---
    areas = [
        ("cadastro_ausencia", "📉 Ausências Justificadas"),
        ("cadastro_parabenizacao", "🎂 Aniversariantes"),
        ("cadastro_visitante", "🫂 Visitantes"),
        ("cadastro_oracao", "🙏 Pedidos de Oração")   
    ]
    for nome_aba, titulo in areas:
        try:
            aba = sh.worksheet(nome_aba)
            d = aba.get_all_records()
            if not d: continue
            df = pd.DataFrame(d)
            
            if "Aprovação" in df.columns: 
                df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", case=False, na=False)]
            
            if nome_aba in ["cadastro_visitante", "cadastro_ausencia"]:
                df, c = converter_coluna_data(df)
                df = df[df[c].dt.date == datetime.now().date()]

            if not df.empty:
                st.markdown(f"### {titulo}")
                
                for _, row in df.iterrows():
                    # Lógica inteligente para achar Nome e Detalhe
                    # Geralmente: [0]Timestamp, [1]Nome, [2]Detalhe/Data
                    
                    val_principal = row.iloc[1] if len(row) > 1 else "" # Nome
                    val_secundario = ""
                    
                    if len(row) > 2:
                        val_secundario = str(row.iloc[2]) # Motivo, Data Nasc, Pedido Oração
                    
                    # Se for Aniversário, formata a data se possível
                    if nome_aba == "cadastro_parabenizacao" and len(val_secundario) > 5:
                        val_secundario = f"Data: {val_secundario}"

                    st.markdown(f"""
                    <div class="info-card">
                        <div class="card-main-text">{val_principal}</div>
                        <div class="card-sub-text">{val_secundario}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
        except: continue

# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    if st.button("🚪 Sair / Logout"): st.session_state["logado"] = False; st.rerun()
    st.markdown("---")
    selected = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={
            "container": {"background-color": "#0e2433"},
            "icon": {"color": "orange", "font-size": "20px"},
            "nav-link": {"color": "white", "font-size": "16px", "text-align": "left", "margin": "0px"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}
        })

# --- ROTEAMENTO ---
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