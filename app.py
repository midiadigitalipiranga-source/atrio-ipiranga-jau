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

# --- FUNÇÃO AUXILIAR: FILTRAR DATA DE HOJE ---
def filtrar_apenas_hoje(df):
    try:
        # Tenta achar a coluna de data (geralmente a primeira ou com nome específico)
        coluna_data = None
        possiveis_nomes = ["Carimbo de data/hora", "Timestamp", "Data", "Date"]
        
        for col in df.columns:
            if col in possiveis_nomes:
                coluna_data = col
                break
        
        if not coluna_data:
            # Se não achou pelo nome, tenta a primeira coluna (padrão do Google Forms)
            coluna_data = df.columns[0]

        # Converte para data
        df[coluna_data] = pd.to_datetime(df[coluna_data], dayfirst=True, errors='coerce')
        
        # Pega a data de hoje
        hoje = datetime.now().date()
        
        # Filtra: mantém apenas onde a data for igual a hoje
        df_hoje = df[df[coluna_data].dt.date == hoje]
        
        return df_hoje
    except Exception as e:
        st.warning(f"Não foi possível filtrar pela data de hoje automaticamente: {e}")
        return df

# --- FUNÇÃO DE GESTÃO (COM LINK E APROVAÇÃO) ---
def mostrar_tabela_gestao(nome_aba_sheets, titulo_na_tela, link_forms=None, filtrar_hoje=False):
    st.header(f"{titulo_na_tela}")
    
    try:
        sh = conectar()
        try:
            aba = sh.worksheet(nome_aba_sheets)
        except:
            st.error(f"Aba '{nome_aba_sheets}' não encontrada na planilha do Google!")
            return

        dados = aba.get_all_records()
        
        if not dados:
            st.warning("A aba existe, mas está vazia.")
            return # Se estiver vazia, para aqui
        else:
            df = pd.DataFrame(dados)
        
        # --- FILTRO DO DIA (SE SOLICITADO) ---
        if filtrar_hoje:
            total_antes = len(df)
            df = filtrar_apenas_hoje(df)
            total_depois = len(df)
            if total_depois == 0 and total_antes > 0:
                st.info(f"Nenhum registro encontrado para HOJE ({datetime.now().strftime('%d/%m/%Y')}). (Total histórico: {total_antes})")
        
        # Se o filtro zerou o dataframe, não mostra editor, só botão
        if df.empty:
             st.warning("Sem dados para exibir com os filtros atuais.")
        else:
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

            # --- BOTÃO SALVAR ---
            if st.button("💾 Salvar Alterações", key=f"btn_{nome_aba_sheets}"):
                with st.spinner("Salvando..."):
                    # Aqui precisamos de um cuidado: O DF editado pode ser menor que o original da planilha
                    # Se filtramos por "hoje", não podemos sobrescrever a planilha toda só com os dados de hoje,
                    # senão apagamos o histórico.
                    # LÓGICA SEGURA: Salvar apenas se NÃO estiver filtrando, ou avisar.
                    
                    if filtrar_hoje:
                        # Para salvar com filtro, é complexo (precisa buscar ID). 
                        # Vamos simplificar: Recarrega TUDO, atualiza as linhas que mudaram (pelo index) ou pede para editar sem filtro.
                        # Por segurança neste código rápido: vamos atualizar TUDO baseando-se na correspondência de linhas se possível.
                        # Mas como o Streamlit não retorna o index original fácil no data_editor filtrado, 
                        # o ideal para edição segura é NÃO filtrar na hora de editar, ou usar banco de dados.
                        #
                        # SOLUÇÃO PARA O SEU CASO AGORA: 
                        # O Streamlit vai atualizar a planilha inteira com o que está na tela.
                        # SE VOCÊ FILTROU, VAI APAGAR O RESTO.
                        # ENTÃO: Vamos impedir salvar quando filtrado por segurança, ou remover o filtro para editar.
                        st.error("⚠️ Para editar e salvar, por favor use a planilha direta ou solicite ao desenvolvedor a lógica de 'Update por ID'. Por segurança, o salvamento está bloqueado na visualização filtrada 'Somente Hoje' para não apagar o histórico.")
                    else:
                        aba.clear()
                        dados_matriz = [df_editado.columns.values.tolist()] + df_editado.values.tolist()
                        aba.update(dados_matriz)
                        st.success("Atualizado!")
        
        # --- BOTÃO NOVO CADASTRO ---
        st.markdown("---")
        if link_forms:
            st.link_button(f"➕ Novo Cadastro (Formulário)", link_forms)

    except Exception as e:
        st.error(f"Erro: {e}")


# --- FUNÇÃO TELA DE APRESENTAÇÃO (COM FILTRO DE DATA E RECADOS) ---
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

    # LISTA DE ORDEM DE APRESENTAÇÃO
    # (Nome da Aba, Título, MENSAGEM)
    areas_para_apresentar = [
        (
            "cadastro_recados", 
            "📌 Recados e Avisos", 
            "Atenção para os recados do dia:" 
        ),
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

            # 1. FILTRO DE STATUS (APROVADO)
            col_status = None
            if "Aprovação" in df.columns: col_status = "Aprovação"
            elif "Status" in df.columns: col_status = "Status"

            if col_status:
                df = df[df[col_status].astype(str).str.contains("Aprovado", case=False, na=False)]

            # 2. FILTRO DE DATA (SOMENTE HOJE)
            # Aplicar filtro de data SOMENTE para: Recados, Visitantes e Ausência
            abas_com_filtro_hoje = ["cadastro_recados", "cadastro_visitante", "cadastro_ausencia"]
            
            if nome_aba in abas_com_filtro_hoje:
                df = filtrar_apenas_hoje(df)

            # SE SOBROU ALGUMA COISA DEPOIS DOS FILTROS, MOSTRA
            if not df.empty:
                st.markdown(f"### {titulo_tela}")
                
                if mensagem_padrao:
                    st.markdown(f"""
                    <div style='
                        background-color: #e8f4f8; 
                        padding: 15px; 
                        border-radius: 5px; 
                        border-left: 6px solid #ffc107; 
                        margin-bottom: 15px;
                    '>
                        <p style='font-size: 22px; color: #0e2433; margin: 0; font-weight: 500;'>
                            🗣️ "{mensagem_padrao}"
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Limpeza visual
                colunas_indesejadas = [col_status, "Carimbo de data/hora", "Timestamp", "Data"]
                df_visual = df.drop(columns=colunas_indesejadas, errors='ignore')
                
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
        options=["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "---", "Apresentação"], 
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "", "cast"], 
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

if selected == "Recados":
    LINK_RECADOS = "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform?usp=publish-editor"
    # Filtrar Hoje = True
    mostrar_tabela_gestao("cadastro_recados", "📌 Recados do Dia", LINK_RECADOS, filtrar_hoje=True)

elif selected == "Visitantes":
    LINK_VISITANTES = "https://docs.google.com/forms/d/e/1FAIpQLScuFOyVP1p0apBrBc0yuOak2AnznpbVemts5JIDe0bawIQIqw/viewform?usp=header"
    # Filtrar Hoje = True
    mostrar_tabela_gestao("cadastro_visitante", "Gestão de Visitantes (Dia)", LINK_VISITANTES, filtrar_hoje=True)

elif selected == "Ausência":
    LINK_AUSENCIA = "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform?usp=header"
    # Filtrar Hoje = True
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