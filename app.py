import os
import streamlit as st
import pandas as pd
import zipfile
import io

# --- 1. IMPORTAÇÃO DO NOVO MÓDULO ---
from src.admin_panel import render_admin_panel 

# --- CONFIGURAÇÃO INICIAL E CORREÇÃO DE DLL (GTK3) ---
gtk3_folder = r"C:\Program Files\GTK3-Runtime Win64\bin"
if os.path.exists(gtk3_folder):
    os.environ['PATH'] = gtk3_folder + os.pathsep + os.environ['PATH']
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(gtk3_folder)

# Importações dos módulos locais
from src.database import *
from src.pdf_generator import gerar_pdf_servidor

# Inicializa banco
init_db()

st.set_page_config(page_title="Seduc Freq System", layout="wide")

# --- CSS PARA DEIXAR BONITO ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- TELA DE LOGIN ---
def login_screen():
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("### 🔐 Acesso ao Sistema")
        st.markdown("---")
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.button("ENTRAR", type="primary"):
            user_data = verificar_login(username, password)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user'] = user_data
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# --- DASHBOARD ADMIN (O USUÁRIO FINAL - SETOR) ---
# (Mantivemos esta função aqui pois é a visão do usuário comum)
def admin_dashboard():
    user = st.session_state['user']
    st.title(f"Setor: {user['setor']}")
    st.caption(f"Logado como: {user['username']}")
    
    tab_equipe, tab_gerar = st.tabs(["🔍 Montar Equipe", "🖨️ Gerar Frequências"])
    
    # ABA 1: BUSCAR
    with tab_equipe:
        st.markdown("#### Buscar Servidor na Base Geral")
        col_busca, col_btn = st.columns([3, 1])
        with col_busca:
            termo = st.text_input("Digite Nome ou Matrícula", placeholder="Ex: MARIA SILVA ou 572...", key="busca_servidor")
        with col_btn:
            st.write("&nbsp;") 
            btn_buscar = st.button("Pesquisar", key="btn_pesquisar_geral")
            
        if termo:
            resultados = buscar_servidores_geral(termo)
            if not resultados.empty:
                st.write(f"Encontrados: {len(resultados)}")
                for index, row in resultados.iterrows():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    c1.write(f"**{row['nome']}**")
                    c2.write(f"{row['matricula']}")
                    c3.write(f"{row['cargo']}")
                    
                    key_btn = f"add_{row['matricula']}_{row['vinculo']}"
                    if c4.button("➕ Adicionar", key=key_btn):
                        adicionar_servidor_ao_admin(row['matricula'], row['vinculo'], user['username'], user['setor'])
                        st.toast(f"{row['nome']} adicionado à equipe!", icon="✅")
                        st.rerun() 
                st.divider()
            else:
                st.warning("Nenhum servidor disponível encontrado com esse nome.")
                
        st.markdown("#### Minha Equipe Atual")
        meus_servidores = get_servidores_por_adm(user['username'])
        if not meus_servidores.empty:
            st.dataframe(meus_servidores[['nome', 'matricula', 'cargo', 'vinculo']], use_container_width=True)
            servidor_remover = st.selectbox("Devolver para o Master (Remover da equipe):", 
                                            meus_servidores['nome'] + " | " + meus_servidores['matricula'],
                                            key="select_remover_equipe")
            if st.button("Remover da Equipe", key="btn_remover_equipe"):
                mat_sel = servidor_remover.split(" | ")[1]
                vinculo_sel = meus_servidores[meus_servidores['matricula'] == mat_sel].iloc[0]['vinculo']
                remover_servidor_do_admin(mat_sel, vinculo_sel)
                st.success("Servidor removido!")
                st.rerun()

    # ABA 2: GERAR PDF COM VERSIONAMENTO
    with tab_gerar:
        meus_servidores = get_servidores_por_adm(user['username'])
        
        if meus_servidores.empty:
            st.warning("Sua equipe está vazia! Vá na aba 'Montar Equipe' para adicionar servidores.")
        else:
            col_cfg, col_table = st.columns([1, 2])
            
            with col_cfg:
                st.header("Configuração")
                mes_nome = st.selectbox("Mês", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"], key="admin_mes_select")
                ano = st.number_input("Ano", value=2026, key="admin_ano_input")
                meses_map = {"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12}
                mes_num = meses_map[mes_nome]
                st.markdown("---")
                st.write("**Feriados e Facultados**")
                feriados = st.multiselect("Dias Feriado", range(1, 32), key="admin_feriados_multi")
                facultados = st.multiselect("Dias Facultado", range(1, 32), key="admin_facultados_multi")

            with col_table:
                st.header("Seleção")
                meus_servidores.insert(0, "Gerar", True)
                edited_df = st.data_editor(meus_servidores, disabled=["matricula", "nome"], hide_index=True, key="admin_data_editor")
                
                if st.button("GERAR DOCUMENTOS 🚀", type="primary", key="btn_gerar_docs"):
                    selecionados = edited_df[edited_df["Gerar"] == True]
                    
                    if not selecionados.empty:
                        bar = st.progress(0, text="Processando...")
                        
                        # --- LOOP DE GERAÇÃO ---
                        pdfs_gerados = [] # Para armazenar em memória se for ZIP
                        
                        total = len(selecionados)
                        for idx, row in enumerate(selecionados.itertuples()):
                            
                            # 1. Obtém a PRÓXIMA VERSÃO do banco
                            versao = obter_proxima_versao(row.matricula, row.vinculo, mes_num, ano)
                            
                            dados = {
                                "nome": row.nome, 
                                "matricula": f"{row.matricula}/{row.vinculo}", 
                                "cargo": row.cargo, 
                                "lotacao": user['setor']
                            }
                            
                            try:
                                # Passa a 'versao' para o gerador
                                pdf_bytes = gerar_pdf_servidor(dados, mes_num, ano, feriados, facultados, versao)
                                
                                pdfs_gerados.append({
                                    "nome_arq": f"{row.nome}_{row.matricula}_{versao}.pdf",
                                    "bytes": pdf_bytes,
                                    "nome_servidor": row.nome
                                })
                                
                            except Exception as e:
                                st.error(f"Erro em {row.nome}: {e}")
                            
                            bar.progress((idx + 1) / total, text=f"Gerando (v{versao}): {row.nome}")

                        # --- DOWNLOAD ---
                        if len(pdfs_gerados) == 1:
                            # Download Único
                            unico = pdfs_gerados[0]
                            st.success(f"Folha de {unico['nome_servidor']} gerada com sucesso!")
                            st.download_button("BAIXAR PDF 📄", data=unico['bytes'], file_name=unico['nome_arq'], mime="application/pdf", key="dl_pdf_unico")
                        
                        elif len(pdfs_gerados) > 1:
                            # Download ZIP
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w") as zf:
                                for item in pdfs_gerados:
                                    zf.writestr(item['nome_arq'], item['bytes'])
                            
                            st.success(f"{len(pdfs_gerados)} documentos gerados!")
                            st.download_button("BAIXAR TUDO (ZIP) 📦", data=zip_buffer.getvalue(), file_name="frequencias_equipe.zip", mime="application/zip", key="dl_zip_multi")
                            
                        bar.empty()

                    else:
                        st.warning("Selecione pelo menos um servidor na tabela!")

# --- ROTEAMENTO ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_screen()
else:
    with st.sidebar:
        st.write(f"👤 **{st.session_state['user']['username']}**")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    # --- 2. AQUI ACONTECE O ROTEAMENTO INTELIGENTE ---
    if st.session_state['user']['role'] == 'master':
        # Chama a função do novo arquivo
        render_admin_panel()
    else:
        # Chama a função local
        admin_dashboard()
