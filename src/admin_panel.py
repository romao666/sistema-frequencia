import streamlit as st
import pandas as pd
from datetime import datetime

# --- DADOS MOCKADOS (Para o visual funcionar antes do Banco de Dados) ---
# Quando o banco estiver 100%, você substituirá isso por SELECTs do SQL
MOCK_DADOS_SETORES = pd.DataFrame({
    "Setor": ["Recursos Humanos", "Gabinete", "Transporte", "Tecnologia (TI)", "Protocolo Geral"],
    "Responsável": ["admin.rh", "admin.gab", "admin.transporte", "admin.ti", "—"],
    "Total Servidores": [50, 12, 30, 8, 15],
    "Folhas Geradas": [50, 6, 0, 8, 0]
})

lista_usuarios_sistema = ["admin.rh", "admin.gab", "admin.transporte", "admin.ti", "joao.romao", "novo.usuario"]

# ==============================================================================
# 1. FUNÇÃO: VISÃO GERAL (DASHBOARD)
# ==============================================================================
def show_visao_geral():
    st.title("🚁 Torre de Controle - Visão Geral")
    st.markdown("---")

    # --- FILTROS ---
    col1, col2 = st.columns([1, 3])
    with col1:
        # Aqui você pode carregar os meses disponíveis no banco
        competencia = st.selectbox("📅 Competência (Mês)", ["01/2026", "12/2025", "11/2025"])
    
    # --- CÁLCULOS DE KPI (Baseado no Mock ou SQL) ---
    df = MOCK_DADOS_SETORES.copy()
    
    # Simula dados diferentes se trocar o mês (só pra visualização)
    if competencia == "12/2025":
        df["Folhas Geradas"] = df["Total Servidores"] # Mês passado tudo 100%
    
    total_servidores = df["Total Servidores"].sum()
    total_gerados = df["Folhas Geradas"].sum()
    total_setores = len(df)
    pendentes = total_servidores - total_gerados
    porcentagem_geral = (total_gerados / total_servidores) * 100 if total_servidores > 0 else 0

    # --- CARDS DE MÉTRICAS (KPIs) ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Total Servidores", f"{total_servidores}")
    k2.metric("🏢 Setores Ativos", f"{total_setores}")
    k3.metric("📄 Folhas Geradas", f"{total_gerados}", f"{porcentagem_geral:.1f}%")
    k4.metric("⚠️ Pendentes", f"{pendentes}", delta_color="inverse")

    st.markdown("### 📊 Progresso da Emissão por Setor")

    # --- TABELA DE PROGRESSO ---
    # Cria a coluna de porcentagem para a barra de progresso
    df["Status (%)"] = (df["Folhas Geradas"] / df["Total Servidores"]) * 100

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status (%)": st.column_config.ProgressColumn(
                "Adesão",
                help="Porcentagem de folhas geradas neste setor",
                format="%.0f%%",
                min_value=0,
                max_value=100,
            ),
            "Responsável": st.column_config.TextColumn(
                "Admin Responsável",
                help="Quem é o chefe deste setor"
            )
        }
    )

# ==============================================================================
# 2. FUNÇÃO: GESTÃO DE SETORES (VINCULAR ADMINS)
# ==============================================================================
def show_gestao_setores():
    st.title("🏢 Gestão de Setores e Acessos")
    st.info("Aqui você cria setores e define quem é o chefe (Admin) responsável por cada um.")
    
    tab1, tab2 = st.tabs(["📋 Lista de Setores", "🔄 Vincular/Trocar Admin"])

    with tab1:
        st.dataframe(MOCK_DADOS_SETORES[["Setor", "Responsável"]], use_container_width=True)

    with tab2:
        st.subheader("Alterar Responsável pelo Setor")
        
        c1, c2, c3 = st.columns([2, 2, 1])
        
        with c1:
            setor_selecionado = st.selectbox("Selecione o Setor", MOCK_DADOS_SETORES["Setor"].unique())
            # Pega o admin atual para mostrar
            admin_atual = MOCK_DADOS_SETORES.loc[MOCK_DADOS_SETORES["Setor"] == setor_selecionado, "Responsável"].values[0]
            st.caption(f"Responsável Atual: **{admin_atual}**")

        with c2:
            novo_admin = st.selectbox("Novo Responsável (Usuário)", lista_usuarios_sistema)

        with c3:
            st.write("") # Espaçamento
            st.write("") 
            if st.button("💾 Salvar Alteração"):
                # AQUI ENTRA O UPDATE NO BANCO DE DADOS
                # query = f"UPDATE setores SET admin_id = ... WHERE nome = '{setor_selecionado}'"
                st.success(f"✅ Sucesso! O usuário **{novo_admin}** agora gerencia o setor **{setor_selecionado}**.")
                st.toast("Alteração salva no banco de dados!")

        st.divider()
        with st.expander("🗑️ Zona de Perigo (Desvincular)"):
            st.warning("Se desvincular, o setor ficará sem ninguém para emitir folhas.")
            if st.button("Desvincular Admin Atual"):
                st.error(f"Admin removido do setor {setor_selecionado}.")

# ==============================================================================
# 3. FUNÇÃO: IMPORTAÇÃO CSV (ETL)
# ==============================================================================
def show_importacao_csv():
    st.title("📂 Importação de Dados (Carga em Lote)")
    st.markdown("Use esta tela para atualizar a base de servidores através do arquivo `.csv` exportado do sistema antigo.")

    uploaded_file = st.file_uploader("Arraste o arquivo CSV aqui", type=["csv"])

    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file, sep=";") # Tente ; ou , dependendo do seu arquivo
            st.success("Arquivo lido com sucesso!")
            
            st.subheader("Pré-visualização dos Dados")
            st.dataframe(df_upload.head())

            st.info(f"O arquivo contém {len(df_upload)} registros.")

            if st.button("🚀 Processar e Salvar no Banco"):
                # AQUI ENTRA A LÓGICA DE INSERT NO BANCO
                # insert_data(df_upload)
                with st.spinner("Importando dados para o Supabase..."):
                    import time
                    time.sleep(2) # Simulação
                st.success("✅ Importação concluída! Os novos servidores já estão disponíveis.")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")

# ==============================================================================
# 4. FUNÇÃO PRINCIPAL (CONTROLADOR)
# ==============================================================================
def render_admin_panel():
    # Menu Lateral
    st.sidebar.markdown("## 👑 Painel Master")
    st.sidebar.info("Logado como: **Super Admin**")
    
    menu = st.sidebar.radio(
        "Navegação",
        ["Visão Geral", "Gestão de Setores", "Importar CSV", "Configurações"],
    )

    # Roteamento das Telas
    if menu == "Visão Geral":
        show_visao_geral()
    elif menu == "Gestão de Setores":
        show_gestao_setores()
    elif menu == "Importar CSV":
        show_importacao_csv()
    elif menu == "Configurações":
        st.title("⚙️ Configurações do Sistema")
        st.write("Configurações globais (Datas de feriados, logotipos, etc).")
