import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread

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

# --- CONEXÃO COM GOOGLE SHEETS (VERSÃO CORRIGIDA PARA NUVEM) ---
@st.cache_resource
def conectar():
    import json
    
    # Abre o arquivo de credenciais
    with open('credentials.json') as f:
        credenciais = json.load(f)
    
    # CORREÇÃO MÁGICA: Arruma a chave privada que costuma quebrar no servidor
    # Ele troca as quebras de linha escritas (\n) por quebras reais
    credenciais['private_key'] = credenciais['private_key'].replace('\\n', '\n')

    # Conecta usando o dicionário corrigido
    gc = gspread.service_account_from_dict(credenciais)
    
    # SEU ID DA PLANILHA
    KEY = "16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I" 
    sh = gc.open_by_key(KEY)
    return sh

# --- FUNÇÃO DE GESTÃO (COM LINK E APROVAÇÃO) ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None):
    st.header(f"{titulo_na_tela}")
    
    try:
        sh = conectar()
        # Tenta abrir a aba. Se não existir, avisa.
        try:
            aba = sh.worksheet(nome_aba_sheets)
        except:
            st.error(f"Aba '{nome_aba_sheets}' não encontrada na planilha do Google!")
            return

        dados = aba.get_all_records()
        
        # Se a aba estiver vazia, cria estrutura básica
        if not dados:
            st.warning("A aba existe, mas está vazia.")
            df = pd.DataFrame(columns=["Data", "Nome", "Aprovação"])
        else:
            df = pd.DataFrame(dados)
        
        # --- LÓGICA DA COLUNA DE APROVAÇÃO ---
        coluna_status = "Aprovação"
        if "Status" in df.columns:
            coluna_status = "Status"
        elif "Aprovação" not in df.columns:
            df["Aprovação"] = ""

        # Organiza colunas (Aprovação primeiro)
        cols = [coluna_status] + [c for c in df.columns if c != coluna_status]
        df = df[cols]

        # --- TABELA EDITÁVEL ---
        df_editado = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{nome_aba_sheets}",
            column_config={
                coluna_status: st.column_config.SelectboxColumn(
                    "Status / Ação",
                    options=["", "✅ Aprovado", "❌ Reprovado", "⚠️ Revisar"],
                    required=True,
                    width="medium"
                )
            }
        )

        # --- BOTÕES (SALVAR + NOVO CADASTRO) ---
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
                with st.spinner("Salvando..."):
                    aba.clear()
                    dados_matriz = [df_editado.columns.values.tolist()] + df_editado.values.tolist()
                    aba.update(dados_matriz)
                    st.success("Atualizado!")
        
        with col2:
            # SÓ MOSTRA O BOTÃO SE TIVER LINK CONFIGURADO
            if link_forms:
                st.link_button(f"➕ Novo Cadastro", link_forms)

    except Exception as e:
        st.error(f"Erro: {e}")


# --- FUNÇÃO TELA DE APRESENTAÇÃO (LEITURA COM DESTAQUE) ---
def mostrar_apresentacao():
    st.markdown("## 📢 Resumo para Leitura")
    
    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Atualizar Lista"):
            st.cache_resource.clear()
            st.rerun()
    
    st.markdown("---")

    sh = conectar()

    # LISTA DE ORDEM DE APRESENTAÇÃO
    # (Nome da Aba, Título, MENSAGEM)
    areas_para_apresentar = [
        (
            "cadastro_ausencia", 
            "📉 Ausências Justificadas", 
            None 
        ),
        (
            "cadastro_eventos", 
            "🗓️ Programação da Semana", 
            "Fiquem atentos aos nossos próximos eventos."
        ),
        (
            "cadastro_parabenizacao", 
            "🎂 Aniversariantes", 
            "Desejamos muitas felicidades e as ricas bênçãos do céu!"
        ),
        (
            "cadastro_visitante", 
            "🫂 Visitantes", 
            "Sejam muito bem-vindos à casa do Senhor! Gostaríamos de conhecê-los."
        ),
        (
            "cadastro_oracao", 
            "🙏 Pedidos de Oração", 
            "Estaremos intercedendo por estas causas durante a semana."
        )  
    ]

    for nome_aba, titulo_tela, mensagem_padrao in areas_para_apresentar:
        try:
            try:
                aba = sh.worksheet(nome_aba)
            except:
                continue

            dados = aba.get_all_records()
            if not dados:
                continue 
                
            df = pd.DataFrame(dados)

            col_status = None
            if "Aprovação" in df.columns: col_status = "Aprovação"
            elif "Status" in df.columns: col_status = "Status"

            if col_status:
                df_aprovados = df[df[col_status].astype(str).str.contains("Aprovado", case=False, na=False)]

                if not df_aprovados.empty:
                    st.markdown(f"### {titulo_tela}")
                    
                    # --- AQUI ESTÁ A MUDANÇA VISUAL ---
                    if mensagem_padrao:
                        # Criamos uma caixa HTML com:
                        # font-size: 22px (Letra Grande)
                        # background-color: #e3f2fd (Fundo azul bem clarinho)
                        # border-left: borda amarela grossa
                        st.markdown(f"""
                        <div style='
                            background-color: #e8f4f8; 
                            padding: 15px; 
                            border-radius: 5px; 
                            border-left: 6px solid #ffc107; 
                            margin-bottom: 15px;
                        '>
                            <p style='
                                font-size: 22px; 
                                color: #0e2433; 
                                margin: 0; 
                                font-weight: 500;
                            '>
                                🗣️ "{mensagem_padrao}"
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # --- LIMPEZA E EXIBIÇÃO ---
                    colunas_indesejadas = [col_status, "Carimbo de data/hora", "Timestamp", "Data"]
                    df_visual = df_aprovados.drop(columns=colunas_indesejadas, errors='ignore')
                    
                    st.dataframe(
                        df_visual, 
                        use_container_width=True, 
                        hide_index=True
                    )
                    st.markdown("---")
        
        except Exception as e:
            continue


# --- MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True) 
    
    selected = option_menu(
        menu_title=None, 
        options=["Visitantes", "Oração", "Parabenização", "Ausência", "Programação", "---", "Apresentação"], 
        icons=["people", "heart", "star", "x-circle", "calendar", "", "cast"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#0e2433"},
            "icon": {"color": "orange", "font-size": "20px"}, 
            "nav-link": {
                "font-size": "16px", "text-align": "left", "margin": "0px", 
                "color": "white", "--hover-color": "#2a4b60"
            },
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"},
        }
    )

# --- CORPO DA PÁGINA ---

if selected == "Visitantes":
    LINK_VISITANTES = "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform?usp=header"
    mostrar_tabela_gestao("cadastro_visitante", "Gestão de Visitantes", LINK_VISITANTES) 

elif selected == "Oração":
    LINK_ORACAO = "https://docs.google.com/forms/d/e/1FAIpQLSe8W9x1Q9AwlSXytO3NDFvi2SgMKpfC6ICTVhMVH92S48KyyQ/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_oracao", "Gestão de Orações", LINK_ORACAO) 

elif selected == "Parabenização":
    LINK_PARABENIZACAO = "https://docs.google.com/forms/d/e/1FAIpQLSdI4ConKeN9T1iKFHTgtO89f71vMXdjrbmdbb20zGK0nMUDtw/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_parabenizacao", "Parabenizações", LINK_PARABENIZACAO)

elif selected == "Ausência":
    LINK_AUSENCIA = "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform?usp=header"
    mostrar_tabela_gestao("cadastro_ausencia", "Justificativas de Ausência", LINK_AUSENCIA)

elif selected == "Programação":
    LINK_EVENTOS = "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform?usp=publish-editor"
    mostrar_tabela_gestao("cadastro_eventos", "Agenda e Eventos da Semana", LINK_EVENTOS)

elif selected == "Apresentação":
    mostrar_apresentacao()