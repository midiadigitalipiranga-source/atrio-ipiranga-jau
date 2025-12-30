# --- FUNÇÃO AUXILIAR: GESTÃO DE RECADOS ---
def gerenciar_recados():
    st.title("📌 Gestão de Recados")
    
    # Botão de Novo Cadastro (Sempre visível)
    st.link_button("➕ Cadastrar Novo Recado (Forms)", "https://docs.google.com/forms/d/e/1FAIpQLSfzuRLtsOTWWThzqFelTAkAwIULiufRmLPMc3BctfEDODY-1w/viewform", use_container_width=True)
    st.markdown("---")

    try:
        sh = conectar()
        aba = sh.worksheet("cadastro_recados")
        dados = aba.get_all_records()
        
        if not dados:
            st.warning("Nenhum recado encontrado.")
            return

        df = pd.DataFrame(dados)

        # 1. Selecionar apenas Colunas B e C (índices 1 e 2)
        # Assumindo: Col B = Quem pede, Col C = Recado
        col_b = df.columns[1]
        col_c = df.columns[2]
        
        # 2. Criar/Verificar coluna de Aprovação (Flag)
        if "Aprovação" not in df.columns:
            df["Aprovação"] = True  # Inicia aprovado (1)
        else:
            # Converte valores da planilha para Booleano (True/False)
            df["Aprovação"] = df["Aprovação"].apply(lambda x: True if str(x) in ['1', 'True', 'VERDADEIRO'] else False)

        # 3. Preparar DataFrame para exibição (Aprovação na frente)
        df_display = df[["Aprovação", col_b, col_c]]

        # --- VISUALIZAÇÃO COLORIDA (PARA CELULAR) ---
        st.markdown("### Visualização de Status")
        for i, row in df_display.iterrows():
            cor_fundo = "#00FF7F" if row["Aprovação"] else "#FFA07A"
            status_texto = "✅ APROVADO" if row["Aprovação"] else "❌ REPROVADO"
            
            st.markdown(f"""
                <div style="background-color: {cor_fundo}; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #ccc; color: #333;">
                    <div style="font-size: 10px; font-weight: bold;">{status_texto}</div>
                    <div style="font-size: 14px; font-weight: bold;">{row[col_b]}</div>
                    <div style="font-size: 16px;">{row[col_c]}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Painel de Controle (Edição)")
        
        # 4. Editor com fonte e Checkbox grande para celular
        df_editado = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Aprovação": st.column_config.CheckboxColumn(
                    "Aprovar?",
                    help="Marque para exibir no telão",
                    default=True,
                    width="medium" # Deixa a coluna mais larga para o polegar
                ),
                col_b: st.column_config.TextColumn("Quem pede", width="medium"),
                col_c: st.column_config.TextColumn("Recado", width="large"),
            },
            key="editor_recados"
        )

        # 5. Botão de Salvar
        if st.button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
            with st.spinner("Atualizando planilha..."):
                # Mesclar edições de volta ao dataframe original
                df.update(df_editado)
                # Converter Booleano de volta para 1 e 0 para o Google Sheets
                df["Aprovação"] = df["Aprovação"].apply(lambda x: 1 if x else 0)
                
                # Atualizar Planilha
                aba.clear()
                aba.update([df.columns.values.tolist()] + df.values.tolist())
                st.success("Planilha atualizada com sucesso!")
                time.sleep(1)
                st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar aba 'cadastro_recados': {e}")

# --- ATUALIZAÇÃO DO ROTEAMENTO ---
if sel == "Recados":
    gerenciar_recados()