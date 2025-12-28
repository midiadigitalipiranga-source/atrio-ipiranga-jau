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
    
    /* Estilo para os cards da Agenda */
    .agenda-card {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #0e2433;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .agenda-time {
        font-weight: bold;
        color: #ffc107;
        font-size: 1.2em;
        background-color: #0e2433;
        padding: 4px 8px;
        border-radius: 4px;
        margin-right: 10px;
    }
    .agenda-title {
        font-weight: bold;
        color: #0e2433;
        font-size: 1.1em;
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

# --- FUNÇÃO AUXILIAR: TRATAR DATA E FILTRAR SEMANA ---
def preparar_dados_agenda(df):
    # 1. Identificar coluna de data
    coluna_data = None
    for col in df.columns:
        if "Data" in col:
            coluna_data = col
            break
    if not coluna_data:
        return pd.DataFrame(), None # Erro se não achar data

    # 2. Identificar coluna de hora
    coluna_hora = None
    for col in df.columns:
        if "Hora" in col or "Horário" in col:
            coluna_hora = col
            break
    
    # 3. Converter data
    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[coluna_data]) # Remove datas inválidas

    # 4. Calcular intervalo da PRÓXIMA SEMANA (Segunda a Domingo)
    hoje = datetime.now().date()
    
    # Lógica: Se hoje é segunda (0), dias_para_segunda = 0. Se hoje é domingo (6), dias = 1.
    # Queremos a semana atual/próxima que começa na segunda-feira mais próxima no futuro (ou hoje)
    dias_para_proxima_segunda = (0 - hoje.weekday() + 7) % 7
    data_inicio_semana = hoje + timedelta(days=dias_para_proxima_segunda)
    data_fim_semana = data_inicio_semana + timedelta(days=6) # Domingo

    # Filtra o DataFrame
    df_semana = df[(df[coluna_data].dt.date >= data_inicio_semana) & (df[coluna_data].dt.date <= data_fim_semana)]
    
    # Ordena por Data e depois por Horário
    if coluna_hora:
        df_semana = df_semana.sort_values(by=[coluna_data, coluna_hora])
    else:
        df_semana = df_semana.sort_values(by=[coluna_data])

    return df_semana, coluna_data

# --- FUNÇÃO DE GESTÃO GENÉRICA (Recados, Visitantes, etc) ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None, filtrar_hoje=False):
    st.header(f"{titulo_na_tela}")
    try:
        sh = conectar()
        try: aba = sh.worksheet(nome_aba_sheets)
        except: st.error(f"Aba '{nome_aba_sheets}' não encontrada!"); return

        dados = aba.get_all_records()
        if not dados:
            st.warning("A aba existe, mas está vazia.")
            if link_forms: st.link_button(f"➕ Novo Cadastro", link_forms); return
        else: df_full = pd.DataFrame(dados)
        
        coluna_status = "Aprovação"
        if "Status" in df_full.columns: coluna_status = "Status"
        elif "Aprovação" not in df_full.columns: df_full["Aprovação"] = ""

        cols = [coluna_status] + [c for c in df_full.columns if c != coluna_status]
        df_full = df_full[cols]

        df_display = df_full.copy()
        
        if filtrar_hoje:
            # Lógica simples de data para gestão
            col_data_nome = "Carimbo de data/hora" if "Carimbo de data/hora" in df_display.columns else df_display.columns[1]
            df_display[col_data_nome] = pd.to_datetime(df_display[col_data_nome], dayfirst=True, errors='coerce')
            hoje = datetime.now().date()
            df_display = df_display[df_display[col_data_nome].dt.date == hoje]
            if df_display.empty: st.info(f"Nenhum registro encontrado para HOJE.")

        df_editado_na_tela = st.data_editor(
            df_display, num_rows="dynamic", use_container_width=True, key=f"editor_{nome_aba_sheets}",
            column_config={
                coluna_status: st.column_config.SelectboxColumn("Status", options=["", "✅ Aprovado", "❌ Reprovado"], required=True, width="medium")
            }
        )

        if not df_editado_na_tela.empty or not filtrar_hoje:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
                    with st.spinner("Salvando..."):
                        df_final = df_full.copy()
                        df_final.update(df_editado_na_tela)
                        if filtrar_hoje: df_final = df_final.astype(str)
                        aba.clear()
                        aba.update([df_final.columns.values.tolist()] + df_final.values.tolist())
                        st.success("Salvo!")
            with col2:
                if link_forms: st.link_button(f"➕ Novo Cadastro", link_forms)
        else:
             if link_forms: st.link_button(f"➕ Novo Cadastro", link_forms)
    except Exception as e: st.error(f"Erro: {e}")

# --- FUNÇÃO ESPECIAL: GESTÃO DA AGENDA SEMANAL ---
def gerenciar_agenda_semanal():
    st.header("🗓️ Programação da Semana")
    
    # 1. MOSTRAR VISUALIZAÇÃO FORMATADA (COMO VAI FICAR NA TELA)
    st.markdown("### 👁️ Visualização da Semana (Segunda a Domingo)")
    
    sh = conectar()
    try: aba = sh.worksheet("cadastro_agenda_semanal")
    except: st.error("Aba 'cadastro_agenda_semanal' não encontrada."); return

    dados = aba.get_all_records()
    link_forms = "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform?usp=publish-editor"

    if not dados:
        st.warning("Sem agenda cadastrada.")
        st.link_button("➕ Adicionar Evento", link_forms)
        return

    df = pd.DataFrame(dados)
    
    # Aplica filtro da semana
    df_semana, col_data = preparar_dados_agenda(df.copy())
    
    if df_semana.empty:
        st.info("Não há eventos cadastrados para a próxima semana fechada (Segunda a Domingo).")
    else:
        # Loop pelos dias da semana (0=Segunda, 6=Domingo)
        dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
        
        for i, nome_dia in enumerate(dias_nomes):
            # Filtra o dia específico
            df_dia = df_semana[df_semana[col_data].dt.weekday == i]
            
            if not df_dia.empty:
                data_formatada = df_dia.iloc[0][col_data].strftime('%d/%m')
                st.subheader(f"{nome_dia} - {data_formatada}")
                
                # Mostra tabela simples para leitura
                cols_visual = ["Horário", "Evento", "Descrição", "Aprovação"]
                # Filtra colunas que existem
                cols_existentes = [c for c in cols_visual if c in df_dia.columns]
                st.dataframe(df_dia[cols_existentes], hide_index=True, use_container_width=True)

    st.markdown("---")
    
    # 2. ÁREA DE EDIÇÃO (TABELA COMPLETA)
    with st.expander("✏️ Editar Agenda Completa (Clique aqui)", expanded=False):
        st.info("Aqui você edita todos os registros. As datas filtram automaticamente a visualização acima.")
        
        # Carrega dados originais para edição
        coluna_status = "Aprovação"
        if "Status" in df.columns: coluna_status = "Status"
        elif "Aprovação" not in df.columns: df["Aprovação"] = ""
        
        # Ordena colunas
        cols = [coluna_status] + [c for c in df.columns if c != coluna_status]
        df = df[cols]

        df_editado = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_agenda_full",
            column_config={
                coluna_status: st.column_config.SelectboxColumn("Status", options=["", "✅ Aprovado", "❌ Reprovado"], required=True)
            }
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Salvar Agenda"):
                with st.spinner("Atualizando..."):
                    df_final = df_editado.astype(str) # Converte tudo para texto para garantir
                    aba.clear()
                    aba.update([df_final.columns.values.tolist()] + df_final.values.tolist())
                    st.success("Agenda atualizada!")
                    time.sleep(1)
                    st.rerun()
        with col2:
            st.link_button("➕ Novo Evento (Formulário)", link_forms)


# --- FUNÇÃO APRESENTAÇÃO ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo do Dia")
    st.markdown(f"**Data:** {datetime.now().strftime('%d/%m/%Y')}")
    if st.button("🔄 Atualizar"):
        st.cache_resource.clear()
        st.rerun()
    st.markdown("---")
    
    sh = conectar()
    
    # --- 1. RECADOS (Com Saudação) ---
    try:
        aba_recados = sh.worksheet("cadastro_recados")
        dados_rec = aba_recados.get_all_records()
        if dados_rec:
            df_rec = pd.DataFrame(dados_rec)
            # Filtro data hoje
            col_data_nome = "Carimbo de data/hora" if "Carimbo de data/hora" in df_rec.columns else df_rec.columns[1]
            df_rec[col_data_nome] = pd.to_datetime(df_rec[col_data_nome], dayfirst=True, errors='coerce')
            hoje = datetime.now().date()
            df_rec = df_rec[df_rec[col_data_nome].dt.date == hoje]
            # Filtro aprovado
            if "Aprovação" in df_rec.columns:
                df_rec = df_rec[df_rec["Aprovação"].astype(str).str.contains("Aprovado", case=False, na=False)]
            
            if not df_rec.empty:
                # SAUDAÇÃO
                st.markdown("""
                <div style='text-align: center; background-color: #0e2433; color: #ffc107; padding: 10px; border-radius: 10px; margin-bottom: 20px; font-size: 20px; font-weight: bold;'>
                    👋 "Cumprimento a igreja com a paz do Senhor!"
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("### 📌 Recados e Avisos")
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Atenção para os recados do dia:</div>", unsafe_allow_html=True)
                cols_indesejadas = ["Aprovação", "Carimbo de data/hora", "Timestamp", "Data"]
                st.dataframe(df_rec.drop(columns=cols_indesejadas, errors='ignore'), use_container_width=True, hide_index=True)
                st.markdown("---")
    except: pass

    # --- 2. AGENDA SEMANAL (FORMATO NOVO) ---
    try:
        aba_agenda = sh.worksheet("cadastro_agenda_semanal")
        dados_ag = aba_agenda.get_all_records()
        if dados_ag:
            df_ag = pd.DataFrame(dados_ag)
            
            # Filtro Aprovado
            if "Aprovação" in df_ag.columns:
                df_ag = df_ag[df_ag["Aprovação"].astype(str).str.contains("Aprovado", case=False, na=False)]

            # Aplica lógica de data (Semana Fechada)
            df_semana, col_data = preparar_dados_agenda(df_ag)

            if not df_semana.empty:
                st.markdown("### 🗓️ Programação da Semana")
                st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ Fiquem atentos aos nossos próximos eventos:</div>", unsafe_allow_html=True)

                dias_nomes = ["Segunda-Feira", "Terça-Feira", "Quarta-Feira", "Quinta-Feira", "Sexta-Feira", "Sábado", "Domingo"]
                
                # Loop para exibir dia a dia
                for i, nome_dia in enumerate(dias_nomes):
                    df_dia = df_semana[df_semana[col_data].dt.weekday == i]
                    
                    if not df_dia.empty:
                        data_str = df_dia.iloc[0][col_data].strftime('%d/%m')
                        st.markdown(f"#### {nome_dia} ({data_str})")
                        
                        # Loop pelos eventos do dia para criar CARDs bonitos
                        for _, row in df_dia.iterrows():
                            horario = row.get("Horário", "--:--")
                            evento = row.get("Evento", "Evento")
                            desc = row.get("Descrição", "")
                            
                            st.markdown(f"""
                            <div class="agenda-card">
                                <span class="agenda-time">⏰ {horario}</span>
                                <span class="agenda-title">{evento}</span>
                                <p style="margin-top: 5px; margin-bottom: 0; color: #555;">{desc}</p>
                            </div>
                            """, unsafe_allow_html=True)
                st.markdown("---")

    except Exception as e: pass

    # --- 3. OUTROS (Ausencia, Parabéns, Visitantes, Oração) ---
    areas_restantes = [
        ("cadastro_ausencia", "📉 Ausências Justificadas", None),
        ("cadastro_parabenizacao", "🎂 Aniversariantes", "Desejamos muitas felicidades!"),
        ("cadastro_visitante", "🫂 Visitantes", "Sejam bem-vindos!"),
        ("cadastro_oracao", "🙏 Pedidos de Oração", "Estaremos intercedendo.")   
    ]
    
    for nome_aba, titulo, msg in areas_restantes:
        try:
            aba = sh.worksheet(nome_aba)
            d = aba.get_all_records()
            if not d: continue
            df = pd.DataFrame(d)
            
            # Filtro Aprovado
            col_aprov = "Aprovação" if "Aprovação" in df.columns else "Status"
            if col_aprov in df.columns:
                 df = df[df[col_aprov].astype(str).str.contains("Aprovado", case=False, na=False)]

            # Filtro Hoje (Para Visitante e Ausencia)
            if nome_aba in ["cadastro_visitante", "cadastro_ausencia"]:
                col_dt_nome = "Carimbo de data/hora" if "Carimbo de data/hora" in df.columns else df.columns[1]
                df[col_dt_nome] = pd.to_datetime(df[col_dt_nome], dayfirst=True, errors='coerce')
                hoje = datetime.now().date()
                df = df[df[col_dt_nome].dt.date == hoje]

            if not df.empty:
                st.markdown(f"### {titulo}")
                if msg: st.markdown(f"<div style='background-color: #e8f4f8; padding: 15px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>🗣️ {msg}</div>", unsafe_allow_html=True)
                
                cols_drop = [col_aprov, "Carimbo de data/hora", "Timestamp", "Data", "Data do Evento"]
                st.dataframe(df.drop(columns=cols_drop, errors='ignore'), use_container_width=True, hide_index=True)
                st.markdown("---")
        except: continue


# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    if st.button("🚪 Sair"): st.session_state["logado"] = False; st.rerun()
    st.markdown("---")
    selected = option_menu(None, ["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], default_index=0,
        styles={"container": {"background-color": "#0e2433"}, "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}})

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
    gerenciar_agenda_semanal() # NOVA FUNÇÃO AQUI
elif selected == "Apresentação":
    mostrar_apresentacao()