import sqlite3
import psycopg2
import pandas as pd
import os
import streamlit as st
from sqlalchemy import create_engine, text

# Tenta pegar a URL do banco dos segredos do Streamlit (Nuvem)
# Se não achar, usa o arquivo local (SQLite)
DB_URL = st.secrets.get("DATABASE_URL", None)
IS_CLOUD = bool(DB_URL)

DB_PATH = "data/sistema.db"

def get_connection():
    """Retorna conexão adequada (Postgres na Nuvem ou SQLite Local)"""
    if IS_CLOUD:
        return psycopg2.connect(DB_URL)
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Comandos SQL adaptáveis
    # Postgres usa SERIAL para auto-incremento, SQLite usa AUTOINCREMENT implícito
    # Mas como sua lógica é simples, TEXT e INTEGER funcionam nos dois.
    
    # Tabela Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    role TEXT,
                    setor_nome TEXT
                )''')
    
    # Tabela Servidores
    c.execute('''CREATE TABLE IF NOT EXISTS servidores (
                    matricula TEXT,
                    nome TEXT,
                    vinculo TEXT,
                    cargo TEXT,
                    setor TEXT,
                    adm_responsavel TEXT,
                    PRIMARY KEY (matricula, vinculo)
                )''')
    
    # Tabela Versões
    c.execute('''CREATE TABLE IF NOT EXISTS versoes_folha (
                    id_unico TEXT PRIMARY KEY,
                    matricula TEXT,
                    vinculo TEXT,
                    mes INTEGER,
                    ano INTEGER,
                    versao_atual INTEGER
                )''')
    
    # Cria Master padrão (Lógica Híbrida para "INSERT OR IGNORE")
    if IS_CLOUD:
        # Sintaxe Postgres
        c.execute("INSERT INTO users VALUES ('master', '123', 'master', 'Geral') ON CONFLICT DO NOTHING")
    else:
        # Sintaxe SQLite
        c.execute("INSERT OR IGNORE INTO users VALUES ('master', '123', 'master', 'Geral')")
        
    conn.commit()
    conn.close()

# --- ADAPTAÇÃO DAS FUNÇÕES DE ESCRITA ---
# O desafio: SQLite usa '?' e Postgres usa '%s' como placeholder.
# Solução: Usamos bibliotecas que abstraem isso ou tratamos manualmente.

def run_query(query, params=(), fetch=False):
    """Função genérica para rodar queries em qualquer banco."""
    conn = get_connection()
    c = conn.cursor()
    
    # Adaptação técnica de placeholders
    if IS_CLOUD:
        query = query.replace('?', '%s')
        # Adaptação de 'INSERT OR IGNORE' para Postgres
        if "INSERT OR IGNORE" in query:
            query = query.replace("INSERT OR IGNORE", "INSERT")
            query += " ON CONFLICT DO NOTHING"
    
    try:
        c.execute(query, params)
        if fetch:
            res = c.fetchall()
            # Converte para DataFrame se for leitura
            col_names = [desc[0] for desc in c.description]
            conn.close()
            return pd.DataFrame(res, columns=col_names)
        else:
            conn.commit()
            conn.close()
            return True, "Sucesso"
    except Exception as e:
        conn.close()
        return False, str(e)

# --- FUNÇÕES DE NEGÓCIO REESCRITAS ---

def criar_usuario(username, password, setor_nome):
    query = "INSERT INTO users VALUES (?, ?, 'admin', ?)"
    # Postgres precisa de tratamento de erro específico para duplicata se não usar ON CONFLICT
    # Mas nossa run_query genérica tenta resolver.
    ok, msg = run_query(query, (username, password, setor_nome))
    if not ok and "duplicate" in msg.lower(): # Tratamento de erro comum
        return False, "Usuário já existe."
    return ok, msg

def listar_usuarios():
    # Pandas read_sql precisa de engine SQLAlchemy para Postgres, 
    # ou conexão direta para SQLite. Vamos simplificar usando nossa run_query
    return run_query("SELECT username, setor_nome FROM users WHERE role = 'admin'", fetch=True)

def excluir_usuario(username):
    run_query("UPDATE servidores SET adm_responsavel = 'master', setor = 'SEM_SETOR' WHERE adm_responsavel = ?", (username,))
    run_query("DELETE FROM users WHERE username = ?", (username,))

def buscar_servidores_geral(termo):
    # LIKE funciona igual nos dois, mas o % precisa ser passado no param
    termo_like = f"%{termo}%"
    return run_query(f"SELECT matricula, nome, vinculo, cargo FROM servidores WHERE adm_responsavel = 'master' AND (nome LIKE ? OR matricula LIKE ?) LIMIT 20", (termo_like, termo_like), fetch=True)

def adicionar_servidor_ao_admin(matricula, vinculo, admin_user, nome_setor):
    run_query("UPDATE servidores SET adm_responsavel = ?, setor = ? WHERE matricula = ? AND vinculo = ?", (admin_user, nome_setor, matricula, vinculo))

def remover_servidor_do_admin(matricula, vinculo):
    run_query("UPDATE servidores SET adm_responsavel = 'master', setor = 'SEM_SETOR' WHERE matricula = ? AND vinculo = ?", (matricula, vinculo))

def get_servidores_por_adm(adm_user):
    return run_query("SELECT * FROM servidores WHERE adm_responsavel = ?", (adm_user,), fetch=True)

def verificar_login(username, password):
    df = run_query("SELECT role, setor_nome FROM users WHERE username = ? AND password = ?", (username, password), fetch=True)
    if not df.empty:
        return {'username': username, 'role': df.iloc[0]['role'], 'setor': df.iloc[0]['setor_nome']}
    return None

def obter_proxima_versao(matricula, vinculo, mes, ano):
    id_unico = f"{matricula}_{vinculo}_{mes}_{ano}"
    df = run_query("SELECT versao_atual FROM versoes_folha WHERE id_unico = ?", (id_unico,), fetch=True)
    
    if not df.empty:
        nova_versao = int(df.iloc[0]['versao_atual']) + 1
        run_query("UPDATE versoes_folha SET versao_atual = ? WHERE id_unico = ?", (nova_versao, id_unico))
        return nova_versao
    else:
        nova_versao = 1
        run_query("INSERT INTO versoes_folha VALUES (?, ?, ?, ?, ?, ?)", (id_unico, matricula, vinculo, mes, ano, nova_versao))
        return nova_versao

def import_csv_to_db(df):
    """
    Importação em massa precisa de performance.
    Para o Postgres, 'to_sql' do Pandas é melhor com SQLAlchemy.
    """
    if IS_CLOUD:
        # Conexão via SQLAlchemy para Pandas
        engine = create_engine(DB_URL)
        
        df.columns = df.columns.str.strip()
        df = df.drop_duplicates(subset=['MATRICULA', 'VINCULO'], keep='first')
        df_db = df[['MATRICULA', 'SERVIDOR', 'VINCULO', 'CARGO']].copy()
        df_db.columns = ['matricula', 'nome', 'vinculo', 'cargo']
        df_db['setor'] = 'SEM_SETOR'
        df_db['adm_responsavel'] = 'master'
        
        try:
            # No Postgres, REPLACE é mais chato. Vamos limpar e inserir.
            # Atenção: Isso apaga tudo para reimportar.
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM servidores"))
                df_db.to_sql('servidores', conn, if_exists='append', index=False, method='multi')
                conn.commit()
            return True, f"Sucesso! {len(df_db)} vínculos importados na Nuvem."
        except Exception as e:
            return False, f"Erro na Nuvem: {e}"
    else:
        # Mantém a lógica SQLite original
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            df.columns = df.columns.str.strip()
            df = df.drop_duplicates(subset=['MATRICULA', 'VINCULO'], keep='first')
            df_db = df[['MATRICULA', 'SERVIDOR', 'VINCULO', 'CARGO']].copy()
            df_db.columns = ['matricula', 'nome', 'vinculo', 'cargo']
            df_db['setor'] = 'SEM_SETOR'
            df_db['adm_responsavel'] = 'master'
            c.execute("DELETE FROM servidores")
            df_db.to_sql('servidores', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            return True, f"Sucesso! {len(df_db)} vínculos importados (Local)."
        except Exception as e:
            conn.close()
            return False, f"Erro Local: {e}"