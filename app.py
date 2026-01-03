import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
import time
import pytz

# --- FUNÇÃO AUXILIAR PARA OBTER DATA BRASIL ---
def obter_hoje_brasil():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).date()

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Átrio - Recepção", layout="wide")

# --- 2. ESTILO VISUAL (Sidebar Azul e Botões Amarelos) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0e2433; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stApp { background-color: #f0f2f6; }
    .stButton > button { background-color: #ffc107; color: #0e2433; border-radius: 10px; font-weight: bold; }
    h3 { color: #0e2433; border-left: 5px solid #ffc107; padding-left: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h1 style='text-align: center;'>🔐 Átrio - Acesso</h1>", unsafe_allow_html=True)
        senha = st.text_input("Digite a senha administrativa:", type="password")
        if st.button("Entrar", use_container_width=True):
            if senha == st.secrets["acesso"]["senha_admin"]:
                st.session_state["logado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# --- 4. CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar():
    cred = json.loads(st.secrets["gcp_service_account"]["credenciais_json"])
    cred['private_key'] = cred['private_key'].replace("\\n", "\n")
    gc = gspread.service_account_from_dict(cred)
    # Sua Planilha Mestra
    return gc.open_by_key("16zFy51tlxGmS-HQklP9_Ath4ZCv-s7Cmd38ayAhGZ_I")

# --- 5. MENU LATERAL ---
with st.sidebar:
    st.image("logo_atrio.png", use_container_width=True)
    sel = option_menu(
        menu_title=None,
        options=["Recados", "Visitantes", "Ausência", "Oração", "Parabenização", "Programação", "Apresentação"],
        icons=["megaphone", "people", "x-circle", "heart", "star", "calendar", "cast"],
        default_index=0,
        styles={
            "container": {"background-color": "#0e2433"},
            "nav-link": {"color": "white", "font-size": "16px", "text-align": "left"},
            "nav-link-selected": {"background-color": "#ffc107", "color": "#0e2433"}
        }
    )


# --- MÓDULO DE RECADOS ---

def gerenciar_recados():
    st.title("📌 Recados de Hoje")
    st.link_button("➕ Novo Cadastro (Forms)", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Sem recados para hoje.")
            return

        # --- LÓGICA DE AUTO-APROVAÇÃO (CORREÇÃO) ---
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            # Se o valor for vazio, 1, True ou VERDADEIRO, vira True. Se for 0 ou False, vira False.
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(
                lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True
            )

        col_b = df_hoje.columns[1] 
        col_c = df_hoje.columns[2] 

        # Cards de Visualização
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f'<div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);"><div style="font-size: 18px; font-weight: bold;">{row[col_b]}</div><div style="font-size: 18px;">{row[col_c]}</div></div>', unsafe_allow_html=True)

        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_b, col_c]],
            use_container_width=True, hide_index=True,
            column_config={"Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small")},
            key="ed_recados"
        )

        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
            df_original.loc[df_hoje.index, col_b] = df_editado[col_b]
            df_original.loc[df_hoje.index, col_c] = df_editado[col_c]
            
            df_para_salvar = df_original.copy()
            df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
            aba.clear()
            aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
            st.success("✅ Sincronizado!")
            time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- MÓDULO DE VISITANTES ---

import pandas as pd
import streamlit as st
import time

def gerenciar_visitantes():
    st.title("🫂 Visitantes de Hoje")
    st.link_button("➕ Novo Visitante", "https://docs.google.com/forms/d/...", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_visitante")
        dados = aba.get_all_records()
        
        if not dados: 
            st.info("Nenhum dado encontrado na planilha.")
            return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        
        # 1. Conversão e Filtro
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhum visitante para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # 2. Correção do Erro de Aprovação
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            # Tratamento seguro para converter valores da planilha em Booleanos
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(
                lambda x: False if str(x).upper() in ['0', 'FALSE', 'FALSO', '0.0'] else True
            )

        col_nome = df_hoje.columns[1]
        col_igreja = df_hoje.columns[2]
        col_convite = df_hoje.columns[3]

        # 3. Visualização em Cards
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f'''
                <div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433;">
                    <div style="font-size: 18px; font-weight: bold;">👤 {row[col_nome]}</div>
                    <div style="font-size: 14px;">CONVITE DE: {row[col_igreja]} | IGREJA: {row[col_convite]}</div>
                </div>
            ''', unsafe_allow_html=True)

        # 4. Editor de Dados
        st.markdown('<div style="margin-top: 50px;"></div>', unsafe_allow_html=True)
        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_nome, col_igreja, col_convite]],
            use_container_width=True, 
            hide_index=True,
            column_config={"Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small")},
            key="ed_visitantes"
        )

        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            # 5. Sincronização cuidadosa
            # Atualizamos o df_original apenas nas linhas que estavam no df_hoje (usando o index)
            df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].values
            df_original.loc[df_hoje.index, col_nome] = df_editado[col_nome].values
            df_original.loc[df_hoje.index, col_igreja] = df_editado[col_igreja].values
            df_original.loc[df_hoje.index, col_convite] = df_editado[col_convite].values
            
            # 6. Preparação para o Google Sheets (Evitar erro de JSON/NaN)
            df_para_salvar = df_original.copy()
            
            # Converte a data de volta para string formatada
            df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
            
            # Substitui valores nulos (NaN) por vazio para não dar erro no update
            df_para_salvar = df_para_salvar.fillna("")
            
            # Limpa e atualiza a planilha
            aba.clear()
            lista_final = [df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist()
            aba.update(lista_final)
            
            st.success("✅ Dados sincronizados com sucesso!")
            time.sleep(1)
            st.rerun()

    except Exception as e:
        st.error(f"Erro crítico: {e}")

# --- MÓDULO DE AUSÊNCIA ---

def gerenciar_ausencia():
    st.title("📉 Ausências de Hoje")
    st.link_button("➕ Justificar Ausência", "https://docs.google.com/forms/d/e/1FAIpQLSdlEV-UIY4L2ElRRL-uZqOUXiEtTfapQ0lkHbK1Fy-H1rcJag/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_ausencia")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhuma ausência registrada para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # Lógica de Aprovação (Vazio ou novo = Ativo/Verde)
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True)

        # Mapeamento de Colunas conforme solicitado
        col_nome = df_hoje.columns[1]   # Col B
        col_cargo = df_hoje.columns[2]  # Col C
        col_motivo = df_hoje.columns[3] # Col D
        col_obs = df_hoje.columns[4]    # Col E

        # Exibição visual nos cards para leitura no Tablet
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            # Montagem do texto conforme sua regra: Nome (Cargo) / Motivo Obs
            st.markdown(f"""
                <div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);">
                    <div style="font-size: 18px; font-weight: bold;">👤 {row[col_nome]} ({row[col_cargo]})</div>
                    <div style="font-size: 18px;">MOTIVO: {row[col_motivo]} | OBS: {row[col_obs]}</div>
                </div>
            """, unsafe_allow_html=True)

        # Painel de Edição
        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_nome, col_cargo, col_motivo, col_obs]],
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                col_nome: "Nome",
                col_cargo: "Cargo",
                col_motivo: "Motivo",
                col_obs: "Observação"
            },
            key="ed_ausencia"
        )

        if st.button("💾 SALVAR AUSÊNCIAS", use_container_width=True):
            with st.spinner("Sincronizando..."):
                # Atualiza Aprovação e campos de texto no DF original
                df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                df_original.loc[df_hoje.index, col_nome] = df_editado[col_nome]
                df_original.loc[df_hoje.index, col_cargo] = df_editado[col_cargo]
                df_original.loc[df_hoje.index, col_motivo] = df_editado[col_motivo]
                df_original.loc[df_hoje.index, col_obs] = df_editado[col_obs]
                
                # Prepara para salvar voltando a data para string
                df_para_salvar = df_original.copy()
                df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
                
                aba.clear()
                aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                st.success("✅ Ausências atualizadas!")
                time.sleep(1); st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar aba 'cadastro_ausencia': {e}")

# --- MÓDULO DE ORAÇÃO ---

def gerenciar_oracao():
    st.title("🙏 Pedidos de Oração")
    st.link_button("➕ Novo Pedido de Oração", "https://docs.google.com/forms/d/e/1FAIpQLSe8W9x1Q9AwlSXytO3NDFvi2SgMKpfC6ICTVhMVH92S48KyyQ/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_oracao")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhum pedido de oração para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # Lógica de Aprovação (Vazio ou novo = Ativo/Verde)
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True)

        # Mapeamento de Colunas
        col_quem = df_hoje.columns[1]   # Col B (Para quem)
        col_motivo = df_hoje.columns[2] # Col C (Motivo)
        col_obs = df_hoje.columns[3]    # Col D (Observação)

        # Exibição visual nos cards
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f"""
                <div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);">
                    <div style="font-size: 18px; font-weight: bold;">🙏 PARA: {row[col_quem]}</div>
                    <div style="font-size: 18px;">MOTIVO: {row[col_motivo]} | OBS: {row[col_obs]}</div>
                </div>
            """, unsafe_allow_html=True)

        # Painel de Edição
        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_quem, col_motivo, col_obs]],
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                col_quem: "Destinatário",
                col_motivo: "Motivo",
                col_obs: "Observação"
            },
            key="ed_oracao"
        )

        if st.button("💾 SALVAR PEDIDOS DE ORAÇÃO", use_container_width=True):
            with st.spinner("Sincronizando..."):
                df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                df_original.loc[df_hoje.index, col_quem] = df_editado[col_quem]
                df_original.loc[df_hoje.index, col_motivo] = df_editado[col_motivo]
                df_original.loc[df_hoje.index, col_obs] = df_editado[col_obs]
                
                df_para_salvar = df_original.copy()
                df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
                
                aba.clear()
                aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                st.success("✅ Pedidos de oração atualizados!")
                time.sleep(1); st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar aba 'cadastro_oracao': {e}")

# --- MÓDULO DE PARABENIZAÇÃO ---

def gerenciar_parabenizacao():
    st.title("🎂 Felicitações de Hoje")
    st.link_button("➕ Nova Felicitação", "https://docs.google.com/forms/d/e/1FAIpQLSdI4ConKeN9T1iKFHTgtO89f71vMXdjrbmdbb20zGK0nMUDtw/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_parabenizacao")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        col_data = df_original.columns[0]
        df_original[col_data] = pd.to_datetime(df_original[col_data], dayfirst=True, errors='coerce')
        
        hoje = obter_hoje_brasil()
        df_hoje = df_original[df_original[col_data].dt.date == hoje].copy()

        if df_hoje.empty:
            st.info(f"📅 Nenhuma felicitação para hoje ({hoje.strftime('%d/%m/%Y')}).")
            return

        # Lógica de Aprovação (Vazio ou novo = Ativo/Verde)
        if "Aprovação" not in df_hoje.columns:
            df_hoje["Aprovação"] = True
        else:
            df_hoje["Aprovação"] = df_hoje["Aprovação"].apply(lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True)

        # Mapeamento de Colunas
        col_nome = df_hoje.columns[1]    # Col B (Quem recebe)
        col_tipo = df_hoje.columns[2]    # Col C (Tipo: Aniversário/Bodas)
        col_obs = df_hoje.columns[3]     # Col D (Observação/Anos)

        # Exibição visual nos cards
        for i, row in df_hoje.iterrows():
            cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            st.markdown(f"""
                <div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 10px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);">
                    <div style="font-size: 18px; font-weight: bold;">✨ {row[col_nome]} ({row[col_tipo]})</div>
                    <div style="font-size: 18px;">INFO: {row[col_obs]}</div>
                </div>
            """, unsafe_allow_html=True)

        # Painel de Edição
        st.markdown("### ⚙️ Painel de Edição")
        df_editado = st.data_editor(
            df_hoje[["Aprovação", col_nome, col_tipo, col_obs]],
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                col_nome: "Homenageado",
                col_tipo: "Tipo",
                col_obs: "Observação/Anos"
            },
            key="ed_parabens"
        )

        if st.button("💾 SALVAR FELICITAÇÕES", use_container_width=True):
            with st.spinner("Sincronizando..."):
                df_original.loc[df_hoje.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                df_original.loc[df_hoje.index, col_nome] = df_editado[col_nome]
                df_original.loc[df_hoje.index, col_tipo] = df_editado[col_tipo]
                df_original.loc[df_hoje.index, col_obs] = df_editado[col_obs]
                
                df_para_salvar = df_original.copy()
                df_para_salvar[col_data] = df_para_salvar[col_data].dt.strftime('%d/%m/%Y %H:%M:%S')
                
                aba.clear()
                aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                st.success("✅ Felicitações atualizadas!")
                time.sleep(1); st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar aba 'cadastro_parabenizacao': {e}")

# --- MÓDULO DE PROGRAMAÇÃO ---

def gerenciar_programacao():
    st.title("🗓️ Programação da Próxima Semana")
    st.link_button("➕ Novo Evento", "https://docs.google.com/forms/d/e/1FAIpQLSc0kUREvy7XDG20tuG55XnaThdZ-nDm5eYp8pdM7M3YKJCPoQ/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_agenda_semanal")
        dados = aba.get_all_records()
        if not dados: return
        
        df_original = pd.DataFrame(dados)
        
        # 1. TRATAMENTO DA DATA DO EVENTO (Coluna B)
        col_evento_data = df_original.columns[1] # Coluna B
        df_original[col_evento_data] = pd.to_datetime(df_original[col_evento_data], dayfirst=True, errors='coerce')

        # 2. CÁLCULO DO INTERVALO (Próxima Segunda a Domingo)
        hoje = obter_hoje_brasil()
        # Dias que faltam para a próxima segunda (0=Segunda, 6=Domingo)
        dias_para_segunda = (0 - hoje.weekday() + 7) % 7
        if dias_para_segunda == 0: dias_para_segunda = 7 # Se hoje é segunda, pula para a próxima
        
        inicio_semana = hoje + timedelta(days=dias_para_segunda)
        fim_semana = inicio_semana + timedelta(days=6)

        # 3. FILTRAGEM
        df_semana = df_original[
            (df_original[col_evento_data].dt.date >= inicio_semana) & 
            (df_original[col_evento_data].dt.date <= fim_semana)
        ].copy()
        
        # Ordenar por data e hora
        df_semana = df_semana.sort_values(by=col_evento_data)

        if df_semana.empty:
            st.info(f"📅 Sem eventos programados para a semana de {inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}.")
            return

        # Lógica de Aprovação
        if "Aprovação" not in df_semana.columns:
            df_semana["Aprovação"] = True
        else:
            df_semana["Aprovação"] = df_semana["Aprovação"].apply(lambda x: False if str(x) in ['0', 'False', 'FALSO'] else True)

        col_evento_nome = df_semana.columns[2] # Coluna C

        # --- EXIBIÇÃO AGRUPADA POR DIA ---
        st.write(f"📅 Exibindo: **{inicio_semana.strftime('%d/%m')}** até **{fim_semana.strftime('%d/%m')}**")
        
        dias_semana_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

        for data_dia, grupo in df_semana.groupby(df_semana[col_evento_data].dt.date):
            nome_dia = dias_semana_pt[data_dia.weekday()]
            st.subheader(f"{nome_dia} ({data_dia.strftime('%d/%m')})")
            
            for i, row in grupo.iterrows():
                cor = "#00FF7F" if row["Aprovação"] else "#FFA07A"
                hora_str = row[col_evento_data].strftime('%H:%M')
                
                st.markdown(f"""
                    <div style="background-color: {cor}; padding: 15px; border-radius: 12px; margin-bottom: 8px; color: #0e2433; border: 1px solid rgba(0,0,0,0.1);">
                        <div style="font-size: 18px; font-weight: bold;">⏰ {hora_str} - {row[col_evento_nome]}</div>
                    </div>
                """, unsafe_allow_html=True)

        # Painel de Edição
        st.markdown("---")
        st.markdown("### ⚙️ Painel de Edição da Semana")
        
        # Criamos uma coluna formatada para o editor mostrar data/hora legível
        df_semana["Horário"] = df_semana[col_evento_data].dt.strftime('%d/%m %H:%M')
        
        df_editado = st.data_editor(
            df_semana[["Aprovação", "Horário", col_evento_nome]],
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn("ATIVO", width="small"),
                "Horário": st.column_config.TextColumn("Data/Hora", disabled=True),
                col_evento_nome: "Evento"
            },
            key="ed_agenda"
        )

        if st.button("💾 SALVAR PROGRAMAÇÃO", use_container_width=True):
            with st.spinner("Sincronizando..."):
                df_original.loc[df_semana.index, "Aprovação"] = df_editado["Aprovação"].apply(lambda x: 1 if x else 0)
                df_original.loc[df_semana.index, col_evento_nome] = df_editado[col_evento_nome]
                
                df_para_salvar = df_original.copy()
                # Converte a data de volta para o formato que o Sheets aceita
                df_para_salvar[col_evento_data] = df_para_salvar[col_evento_data].dt.strftime('%d/%m/%Y %H:%M:%S')
                
                aba.clear()
                aba.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                st.success("✅ Agenda atualizada!")
                time.sleep(1); st.rerun()

    except Exception as e:
        st.error(f"Erro na Programação: {e}")
  
# --- TELA DE APRESENTAÇÃO (RESUMO FINAL PARA LEITURA) ---

def mostrar_apresentacao():
    # 1. SAUDAÇÃO INICIAL FIXA
    st.markdown("""
        <div style="background-color: #0e2433; padding: 25px; border-radius: 15px; text-align: center; margin-bottom: 40px;">
            <h1 style="color: #ffc107; margin: 0; font-size: 28px;">"CUMPRIMENTO A IGREJA COM A PAZ DO SENHOR"</h1>
        </div>
    """, unsafe_allow_html=True)

    try:
        sh = conectar()
        hoje = obter_hoje_brasil()
        
        # Função para padronizar os cartões (Fonte 18px neutra)
        def renderizar_cartao(conteudo):
            st.markdown(f"""
                <div style="background-color: #ffffff; padding: 18px; border-radius: 12px; margin-bottom: 12px; border: 1px solid #ddd; border-left: 8px solid #0e2433;">
                    <div style="font-size: 18px; color: #0e2433; line-height: 1.5;">{conteudo}</div>
                </div>
            """, unsafe_allow_html=True)

        # Função de segurança para carregar e filtrar dados
        def carregar_dados_seguro(aba_nome, data_idx=0, filtrar_hoje=True):
            try:
                df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records())
                if df.empty: return pd.DataFrame()
                
                # Tratamento da Data (limpa hora do carimbo)
                df[df.columns[data_idx]] = pd.to_datetime(df[df.columns[data_idx]], dayfirst=True, errors='coerce').dt.date
                
                # Filtro de Aprovação (Trata erro 'Aprovação')
                if "Aprovação" in df.columns:
                    df = df[~df["Aprovação"].astype(str).isin(['0', 'False', 'FALSO'])]
                
                # Filtro de Hoje
                if filtrar_hoje:
                    df = df[df[df.columns[data_idx]] == hoje]
                return df
            except: return pd.DataFrame()

        # --- SETOR 1: AUSÊNCIAS ---
        df_aus = carregar_dados_seguro("cadastro_ausencia")
        if not df_aus.empty:
            st.info("💡 JUSTIFICANDO A AUSÊNCIA DE ALGUMAS PESSOAS")
            for _, r in df_aus.iterrows():
                renderizar_cartao(f"<b>👤 {r.iloc[1]} ({r.iloc[2]})</b><br>MOTIVO: {r.iloc[3]} | {r.iloc[4]}")
            st.markdown("<br><br>", unsafe_allow_html=True)

        # --- SETOR 2: PROGRAMAÇÃO (SÓ DOMINGO) ---
        if hoje.weekday() == 6: # 6 é Domingo
            df_prog = pd.DataFrame(sh.worksheet("cadastro_agenda_semanal").get_all_records())
            if not df_prog.empty:
                col_ev = df_prog.columns[1] # Coluna B
                df_prog[col_ev] = pd.to_datetime(df_prog[col_ev], dayfirst=True, errors='coerce')
                
                # Próxima Semana
                dias_seg = (0 - hoje.weekday() + 7) % 7
                if dias_seg == 0: dias_seg = 7
                ini, fim = hoje + timedelta(days=dias_seg), hoje + timedelta(days=dias_seg+6)
                
                df_p = df_prog[(df_prog[col_ev].dt.date >= ini) & (df_prog[col_ev].dt.date <= fim)]
                if "Aprovação" in df_p.columns:
                    df_p = df_p[~df_p["Aprovação"].astype(str).isin(['0', 'False', 'FALSO'])]
                
                if not df_p.empty:
                    st.warning("📣 VAMOS AGORA A PROGRAMAÇÃO DA SEMANA")
                    dias_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
                    for data_dia, grupo in df_p.sort_values(by=col_ev).groupby(df_p[col_ev].dt.date):
                        st.markdown(f"**{dias_pt[data_dia.weekday()]} ({data_dia.strftime('%d/%m')})**")
                        for _, r in grupo.iterrows():
                            st.markdown(f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 8px; border-left: 5px solid #0e2433; margin-bottom: 5px; font-size: 18px;"><b>⏰ {r[col_ev].strftime("%H:%M")}</b> - {r.iloc[2]}</div>', unsafe_allow_html=True)
                    st.markdown("<br><br>", unsafe_allow_html=True)

        # --- SETOR 3: RECADOS ---
        df_rec = carregar_dados_seguro("cadastro_recados")
        if not df_rec.empty:
            st.info("💡 VAMOS AGORA PARA OS RECADOS SOLICITADOS")
            for _, r in df_rec.iterrows():
                renderizar_cartao(f"<b>💬 {r.iloc[2]}</b><br><small>Solicitante: {r.iloc[1]}</small>")
            st.markdown("<br><br>", unsafe_allow_html=True)

        # --- SETOR 4: ANIVERSÁRIOS ---
        df_par = carregar_dados_seguro("cadastro_parabenizacao")
        if not df_par.empty:
            st.success("🎂 A ASSEMBLEIA MINISTÉRIO IPIRANGA PARABENIZA A:")
            for _, r in df_par.iterrows():
                renderizar_cartao(f"<b>✨ {r.iloc[1]} ({r.iloc[2]})</b><br>{r.iloc[3]}")
            st.markdown("<br><br>", unsafe_allow_html=True)

        # --- SETOR 5: VISITANTES ---
        df_vis = carregar_dados_seguro("cadastro_visitante")
        if not df_vis.empty:
            st.warning("🫂 VAMOS CONHECER NOSSOS VISITANTES DE HOJE:")
            st.markdown("**CONFORME EU CHAMAR GOSTARIA QUE DESSEM UM SINAL COM A MÃO OU FIQUEM EM PÉ PARA QUE A IGREJA OS VEJAM.**")
            for _, r in df_vis.iterrows():
                renderizar_cartao(f"<b>👤 {r.iloc[1]}</b><br>CONVITE DE: {r.iloc[2]} | IGREJA: {r.iloc[3]}")
            
            st.markdown("""
                <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px solid #0e2433; margin-top: 15px;">
                    <p style="font-size: 18px;"><b>PEÇO QUE A IGREJA SE COLOQUEM EM PÉ PARA RECEBERMOS NOSSOS VISITANTES COM UM ABRAÇO, UM SORRISO E UM APERTO DE MÃO.</b></p>
                    <p style="font-size: 19px; color: #0e2433; font-weight: bold;">TODOS JUNTOS, COMO VAMOS RECEBER OS VISITANTES?</p>
                    <p style="font-size: 18px; color: #d32f2f; font-weight: bold;">SEJAM BEM VINDOS EM NOME DE JESUS, SINTAM-SE BEM, VOLTEM SEMPRE, JESUS OS AMA E NÓS TAMBÉM.</p>
                    <p style="text-align: center; font-style: italic; margin-top: 10px;">🎶 """ + '"CORINHO COM A BASE MUSICAL"' + """</p>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("<br><br>", unsafe_allow_html=True)

        # --- SETOR 6: ORAÇÃO ---
        df_ora = carregar_dados_seguro("cadastro_oracao")
        if not df_ora.empty:
            st.markdown("<h3 style='text-align: center;'>🙏 """ + '""COM A IGREJA EM PÉ""' + """</h3>""", unsafe_allow_html=True)
            st.info("TEMOS ALGUNS PEDIDOS DE ORAÇÃO")
            for _, r in df_ora.iterrows():
                renderizar_cartao(f"<b>🙏 PARA: {r.iloc[1]}</b><br>MOTIVO: {r.iloc[2]} | OBS: {r.iloc[3]}")
            st.markdown("<p style='text-align: center; font-weight: bold; font-size: 19px;'>PARA ORAR POR ESTES PEDIDOS VOU CHAMAR O...</p>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erro ao carregar roteiro de Apresentação: {e}")
                
# --- ATUALIZAÇÃO DO ROTEAMENTO ---

if sel == "Recados":
    gerenciar_recados()
    
elif sel == "Visitantes":
    gerenciar_visitantes()
    
elif sel == "Ausência":
    gerenciar_ausencia()
    
elif sel == "Oração":
    gerenciar_oracao()
    
elif sel == "Parabenização":
    gerenciar_parabenizacao()

if sel == "Programação":
    gerenciar_programacao()

elif sel == "Apresentação":
    # Agora chamamos a função que consolida todos os dados ativos
    mostrar_apresentacao()