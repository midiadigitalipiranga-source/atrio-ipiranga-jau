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
    
    /* Força cor branca em todos os elementos da sidebar */
    [data-testid="stSidebar"] * { color: white !important; }
    
    .stApp { background-color: #f0f2f6; }
    
    /* Botões Amarelos */
    .stButton > button {
        background-color: #ffc107; color: #0e2433;
        border-radius: 10px; border: none; font-weight: bold;
    }
    
    /* Títulos */
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }

    /* --- Estilo para os Cards da Agenda --- */
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
            # Tenta pegar a hora se for formato datetime "YYYY-MM-DD HH:MM:SS"
            parte_hora = valor.split(" ")[-1]
            if ":" in parte_hora:
                return parte_hora[:5] # Retorna HH:MM
        except: pass
    return "⏰" # Retorna ícone se não achar hora

# --- FUNÇÃO AUXILIAR: FILTRAR SEMANA ---
def filtrar_proxima_semana(df):
    # Procura especificamente a coluna "Data do Evento" ou que tenha "Data"
    coluna_data = None
    for col in df.columns:
        if "Data" in col and "Carimbo" not in col:
            coluna_data = col
            break
    
    # Se não achou, pega a coluna índice 1 (assumindo que 0 é timestamp)
    if not coluna_data and len(df.columns) > 1:
        coluna_data = df.columns[1]
    
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

        # Checkbox Reprovar
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

# --- FUNÇÃO GESTÃO DA PROGRAMAÇÃO (3 COLUNAS) ---
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
    
    # Filtro Aprovação (se existir a coluna, usa. Se não, mostra tudo)
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
                    # --- CORREÇÃO DEFINITIVA (3 COLUNAS) ---
                    # Layout: [0] Carimbo, [1] Data, [2] Descrição
                    
                    val_timestamp = row.iloc[0] # Índice 0
                    
                    # Tenta pegar hora da coluna de data (índice 1) ou põe ícone
                    val_hora_destaque = limpar_hora(row.iloc[1]) 
                    
                    # Descrição é a coluna 2 (índice 2)
                    # Verifica se existe coluna 2 para não dar erro IndexOutOfRange
                    val_descricao = row.iloc[2] if len(row) > 2 else "Evento sem descrição"
                    
                    st.markdown(f"""
                    <div class="agenda-card">
                        <span class="agenda-col-c">{val_hora_destaque}</span>
                        <span class="agenda-col-d">{val_descricao}</span>
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

# --- FUNÇÃO APRESENTAÇÃO ---
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
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Atenção para os recados do dia:</div>", unsafe_allow_html=True)
                cols_drop = ["Aprovação", "Carimbo de data/hora", "Timestamp", "Data"]
                st.dataframe(df.drop(columns=cols_drop, errors='ignore'), use_container_width=True, hide_index=True)
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
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Fiquem atentos aos nossos próximos eventos:</div>", unsafe_allow_html=True)
                
                dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
                
                for i, nome_dia in enumerate(dias_nomes):
                    df_dia = df_semana[df_semana[col_data].dt.weekday == i]
                    if not df_dia.empty:
                        data_str = df_dia.iloc[0][col_data].strftime('%d/%m')
                        st.markdown(f"#### {nome_dia} ({data_str})")
                        
                        for _, row in df_dia.iterrows():
                            # --- LEITURA SEGURA (3 COLUNAS) ---
                            # [0] Carimbo, [1] Data, [2] Descrição
                            
                            val_hora = limpar_hora(row.iloc[1]) # Tenta hora da coluna data
                            val_desc = row.iloc[2] if len(row) > 2 else "Evento"
                            
                            st.markdown(f"""
                            <div class="agenda-card">
                                <span class="agenda-col-c">{val_hora}</span>
                                <span class="agenda-col-d">{val_desc}</span>
                            </div>
                            """, unsafe_allow_html=True)
                st.markdown("---")
    except: pass

    # --- 3. OUTROS ---
    areas = [
        ("cadastro_ausencia", "📉 Ausências Justificadas", None),
        ("cadastro_parabenizacao", "🎂 Aniversariantes", "Desejamos muitas felicidades!"),
        ("cadastro_visitante", "🫂 Visitantes", "Sejam bem-vindos!"),
        ("cadastro_oracao", "🙏 Pedidos de Oração", "Estaremos intercedendo.")   
    ]
    for nome, titulo, msg in areas:
        try:
            aba = sh.worksheet(nome)
            d = aba.get_all_records()
            if not d: continue
            df = pd.DataFrame(d)
            
            if "Aprovação" in df.columns: 
                df = df[~df["Aprovação"].astype(str).str.contains("Reprovado", case=False, na=False)]
            
            if nome in ["cadastro_visitante", "cadastro_ausencia"]:
                df, c = converter_coluna_data(df)
                df = df[df[c].dt.date == datetime.now().date()]

            if not df.empty:
                st.markdown(f"### {titulo}")
                if msg: st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ {msg}</div>", unsafe_allow_html=True)
                st.dataframe(df.drop(columns=["Aprovação", "Carimbo de data/hora", "Timestamp", "Data", "Data do Evento"], errors='ignore'), use_container_width=True, hide_index=True)
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