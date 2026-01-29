from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import qrcode
import io
import base64
from datetime import date, timedelta
import pandas as pd
import os
import hashlib
import json # Importante para criar o JSON da IA

def gerar_qr_code_base64(dados_json):
    """Gera QR Code contendo JSON estruturado para Visão Computacional."""
    # Transforma o dicionário em string JSON
    texto_qr = json.dumps(dados_json, separators=(',', ':'))
    
    qr = qrcode.QRCode(version=1, box_size=5, border=1) 
    qr.add_data(texto_qr)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"

def calcular_dias(mes, ano, feriados_dias, facultados_dias):
    """Lógica de dias (Mantida igual)."""
    dias = []
    if mes == 12: proximo_mes = date(ano + 1, 1, 1)
    else: proximo_mes = date(ano, mes + 1, 1)
    ultimo_dia = (proximo_mes - timedelta(days=1)).day
    nomes_semana = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA", "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]

    for d in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, d)
        idx_semana = data_atual.weekday()
        info = {"dia": d, "semana": nomes_semana[idx_semana], "ehUtil": True, "textoMesclado": ""}

        if d in feriados_dias:
            info["ehUtil"] = False; info["textoMesclado"] = "FERIADO"
        elif d in facultados_dias:
            info["ehUtil"] = False; info["textoMesclado"] = "FACULTADO"
        elif idx_semana == 5:
            info["ehUtil"] = False; info["textoMesclado"] = "SÁBADO"
        elif idx_semana == 6:
            info["ehUtil"] = False; info["textoMesclado"] = "DOMINGO"
        dias.append(info)
    return dias

def gerar_pdf_servidor(dados_servidor, mes, ano, feriados, facultados, versao_doc):
    """
    Agora recebe 'versao_doc' para colocar no QR Code.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('folha_ponto.html')
    
    # Separa Matrícula e Vínculo (assumindo formato "12345/1")
    if '/' in dados_servidor['matricula']:
        mat_pura, vinculo = dados_servidor['matricula'].split('/')
    else:
        mat_pura, vinculo = dados_servidor['matricula'], "1"

    # --- DADOS PARA A IA (Payload JSON) ---
    payload_ia = {
        "m": mat_pura,       # Matrícula
        "vi": vinculo,       # Vínculo
        "nm": dados_servidor['nome'], # Nome (Opcional, mas bom pra debug)
        "st": dados_servidor['lotacao'], # Setor
        "cg": dados_servidor['cargo'],   # Cargo
        "ref": f"{mes}/{ano}", # Mês/Ano
        "v": versao_doc      # VERSÃO DO DOCUMENTO (Ouro!)
    }
    
    # Gera QR Code com JSON
    qr_url = gerar_qr_code_base64(payload_ia)
    
    # Calcula dias
    lista_dias = calcular_dias(mes, ano, feriados, facultados)
    
    meses_nome = ["", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
    
    # Renderiza HTML
    html_str = template.render(
        dados=dados_servidor,
        mesAno=f"{meses_nome[mes]}/{ano}",
        qrCodeUrl=qr_url, 
        dias=lista_dias
    )
    
    pdf_file = HTML(string=html_str, base_url=base_dir).write_pdf()
    return pdf_file