import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA (TELA CHEIA) ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- CSS PERSONALIZADO (A MAQUIAGEM) ---
st.markdown("""
<style>
    /* Cor de fundo da barra lateral */
    [data-testid="stSidebar"] {
        background-color: #0e2433; /* Azul escuro da imagem */
    }
    /* Texto da barra lateral */
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    /* Fundo principal */
    .stApp {
        background-color: #f0f2f6; /* Cinza claro texturizado */
    }
    /* Botões padrão do Streamlit */
    .stButton > button {
        background-color: #ffc107; /* Amarelo */
        color: #0e2433; /* Azul texto */
        border-radius: 10px;
        border: none;
        font-weight: bold;
    }
    /* Títulos da apresentação */
    h3 {
        color: #0e2433;
        border-left: 5px solid #ffc107;
        padding-left: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM GOOGLE SHEETS (VERSÃO BLINDADA) ---
@st.cache_resource
def conectar():
    # Busca a credencial no cofre
    texto_credenciais = st.secrets["gcp_service_account"]["credenciais_json"]
    
    # Converte de texto para dicionário
    credenciais = json.loads(texto_credenciais)
    
    # TRATAMENTO DE CHOQUE NA CHAVE:
    chave_privada = credenciais['private_key']
    if "\\n" in chave_privada:
        chave_privada = chave_privada.replace("\\n", "\n")
    credenciais['private_key'] = chave_privada

    # Conecta
    gc = gspread.service_account_from_dict(credenciais)
    
    # SEU ID DA PLANILHA
    KEY = "16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I" 
    sh = gc.open_by_key(KEY)
    return sh

# --- FUNÇÃO AUXILIAR: IDENTIFICAR DATA ---
def converter_coluna_data(df):
    # Tenta achar a coluna de data
    coluna_data = None
    possiveis_nomes = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
    
    for col in df.columns:
        if col in possiveis_nomes:
            coluna_data = col
            break
    
    if not coluna_data:
        # Se não achou pelo nome, tenta a primeira coluna
        coluna_data = df.columns[0]

    # Converte para data
    df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
    return df, coluna_data

# --- FUNÇÃO DE GESTÃO (COM SALVAMENTO INTELIGENTE) ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None, filtrar_hoje=False):
    st.header(f"{titulo_na_tela}")
    
    try:
        sh = conectar()
        try:
            aba = sh.worksheet(nome_aba_sheets)
        except:
            st.error(f"Aba '{nome_aba_sheets}' não encontrada na planilha do Google!")
            return

        # 1. CARREGA TUDO (HISTÓRICO COMPLETO)
        dados = aba.get_all_records()
        
        if not dados:
            st.warning("A aba existe, mas está vazia.")
            # Botão de novo cadastro mesmo vazia
            if link_forms:
                st.markdown("---")
                st.link_button(f"➕ Novo Cadastro (Formulário)", link_forms)
            return
        else:
            # Cria DataFrame COMPLETO
            df_full = pd.DataFrame(dados)
        
        # --- LÓGICA DA COLUNA DE APROVAÇÃO ---
        coluna_status = "Aprovação"
        if "Status" in df_full.columns:
            coluna_status = "Status"
        elif "Aprovação" not in df_full.columns:
            df_full["Aprovação"] = "" # Cria se não existir

        # Organiza colunas no DF Completo
        cols = [coluna_status] + [c for c in df_full.columns if c != coluna_status]
        df_full = df_full[cols]

        # 2. APLICA O FILTRO DE DATA (SE NECESSÁRIO) PARA EXIBIÇÃO
        df_display = df_full.copy() # Cópia para mostrar na tela
        
        if filtrar_hoje:
            df_display, col_data_nome = converter_coluna_data(df_display)
            hoje = datetime.now().date()
            
            # Filtra mantendo o INDEX original (importante para salvar depois!)
            df_display = df_display[df_display[col_data_nome].dt.date == hoje]
            
            if df_display.empty:
                 st.info(f"Nenhum registro encontrado para HOJE ({hoje.strftime('%d/%m/%Y')}).")

        # --- TABELA EDITÁVEL ---
        # O data_editor retorna apenas as linhas que estão na tela, mas preserva o Índice (ID) original
        df_editado_na_tela = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{nome_aba_sheets}",
            column_config={
                coluna_status: st.column_config.SelectboxColumn(
                    "Status / Ação",
                    options=["", "✅ Aprovado", "❌ Reprovado", "⚠️ Revisar"],
                    required=True,
                    width="medium"
                ),
                # Se filtrou data, formata a coluna de data para ficar bonita
                **( {col_data_nome: st.column_config.DateColumn("Data", format="DD/MM/YYYY")} if filtrar_hoje and not df_display.empty else {} )
            }
        )

        # --- BOTÃO SALVAR INTELIGENTE ---
        # Só mostra o botão se tiver dados na tela ou se não estiver filtrando
        if not df_editado_na_tela.empty or not filtrar_hoje:
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
                    with st.spinner("Salvando com segurança..."):
                        
                        # A MÁGICA DO UPDATE:
                        # 1. Pegamos o DF Completo (df_full)
                        # 2. Atualizamos ele com as linhas que foram editadas na tela (df_editado_na_tela)
                        #    O Pandas usa o número da linha (index) para saber quem é quem.
                        
                        # Precisamos garantir que as datas voltem a ser texto para o JSON aceitar
                        df_final_para_salvar = df_full.copy()
                        
                        # Atualiza o df_full com as edições feitas na tela
                        df_final_para_salvar.update(df_editado_na_tela)
                        
                        # Se usamos conversão de data, converte tudo para string antes de enviar para evitar erro de JSON
                        if filtrar_hoje:
                            # Converte colunas de data/tempo para string
                            df_final_para_salvar = df_final_para_salvar.astype(str)

                        # Limpa a aba e escreve TUDO de novo (Histórico + Edições de hoje)
                        aba.clear()
                        dados_matriz = [df_final_para_salvar.columns.values.tolist()] + df_final_para_salvar.values.tolist()
                        aba.update(dados_matriz)
                        
                        st.success("Atualizado com sucesso! (Histórico preservado)")
            
            with col2:
                if link_forms:
                    st.link_button(f"➕ Novo Cadastro", link_forms)
        
        else:
             # Se está vazio (hoje), mostra só o botão de novo
             if link_forms:
                st.link_button(f"➕ Novo Cadastro", link_forms)

    except Exception as e:
        st.error(f"Erro: {e}")


# --- FUNÇÃO TELA DE APRESENTAÇÃO ---
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

    areas_para_apresentar = [
        ("cadastro_recados", "📌 Recados e Avisos", "Atenção para os recados do dia:"),
        ("cadastro_ausencia", "📉 Ausências Justificadas", None),
        ("cadastro_eventos", "🗓️ Programação da Semana", "Fiquem atentos aos nossos próximos eventos."),
        ("cadastro_parabenizacao", "🎂 Aniversariantes", "Desejamos muitas felicidades e as ricas bênçãos do céu!"),
        ("cadastro_visitante", "🫂 Visitantes", "Sejam muito bem-vindos à casa do Senhor! Gostaríamos de conhecê-los."),
        ("cadastro_oracao", "🙏 Pedidos de Oração", "Estaremos intercedendo por estas causas durante a semana.")   
    ]

    for nome_aba, titulo_tela, mensagem_padrao in areas_para_apresentar:
        try:
            try:
                aba = sh.worksheet(nome_aba)
            except:
                continue

            dados = aba.get_all_records()
            if not dados: continue 
                
            df = pd.DataFrame(dados)

            # 1. FILTRO DE STATUS
            col_status = None
            if "Aprovação" in df.columns: col_status = "Aprovação"
            elif "Status" in df.columns: col_status = "Status"

            if col_status:
                df = df[df[col_status].astype(str).str.contains("Aprovado", case=False, na=False)]

            # 2. FILTRO DE DATA (SOMENTE HOJE) PARA ABAS ESPECÍFICAS
            abas_com_filtro_hoje = ["cadastro_recados", "cadastro_visitante", "cadastro_ausencia"]
            
            if nome_aba in abas_com_filtro_hoje:
                df, col_data = converter_coluna_data(df)
                hoje = datetime.now().date()
                df = df[df[col_data].dt.date == hoje]

            # EXIBIÇÃO
            if not df.empty:
                st.markdown(f"### {titulo_tela}")
                
                if mensagem_padrao:
                    st.markdown(f"""
                    <div style='background-color: #e8f4f8; padding: 15px; border-radius: 5px; border-left: 6px solid #ffc107; margin-bottom: 15px;'>
                        <p style='font-size: 22px; color: #0e2433; margin: 0; font-weight: 500;'>🗣️ "{mensagem_padrao}"</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                colunas_indesejadas = [col_status, "Carimbo de data/hora", "Timestamp", "Data"]
                df_visual = df.drop(columns=colunas_indesejadas, errors='ignore')
                
                # Formata datas se sobrarem na visualização
                st.dataframe(df_visual, use_container_width=True, hide_index=True)
                st.markdown("---")
        
        except Exception as e:
            continue

# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    
    selected = option_menu(
        menu_title=None, 
        options=["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#0e2433"},
            "icon": {"color": "orange", "font-size": "20px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "color": "white", "--hover-color": "#2a4b60"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"},
        }
    )

# --- CORPO DA PÁGINA ---
if selected == "Recados":
    LINK_RECADOS = "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_recados", "📌 Recados do Dia", LINK_RECADOS, filtrar_hoje=True)

elif selected == "Visitantes":
    LINK_VISITANTES = "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform?usp=header"
    mostrar_tabela_gestao("cadastro_visitante", "Gestão de Visitantes (Dia)", LINK_VISITANTES, filtrar_hoje=True)

elif selected == "Ausência":
    LINK_AUSENCIA = "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform?usp=header"
    mostrar_tabela_gestao("cadastro_ausencia", "Justificativas de Ausência (Dia)", LINK_AUSENCIA, filtrar_hoje=True)

elif selected == "Oração":
    LINK_ORACAO = "https://docs.google.com/forms/d/e/1FAIpQLSe8W9x1Q9AwlSXytO3NDFvi2SgMKpfC6ICTVhMVH92S48KyyQ/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_oracao", "Gestão de Orações", LINK_ORACAO) 

elif selected == "Parabenização":
    LINK_PARABENIZACAO = "https://docs.google.com/forms/d/e/1FAIpQLSdI4ConKeN9T1iKFHTgtO89f71vMXdjrbmdbb20zGK0nMUDtw/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_parabenizacao", "Parabenizações", LINK_PARABENIZACAO)

elif selected == "Programação":
    LINK_EVENTOS = "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_eventos", "Agenda e Eventos da Semana", LINK_EVENTOS)

elif selected == "Apresentação":
    mostrar_apresentacao()