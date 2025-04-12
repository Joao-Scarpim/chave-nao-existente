import pyodbc
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import logging

# === CONFIGURAÇÃO DO LOG ===
log_dir = "logs_chave_nao_existente"
os.makedirs(log_dir, exist_ok=True)
log_filename = datetime.now().strftime("log_%Y-%m-%d.txt")
log_path = os.path.join(log_dir, log_filename)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.info

load_dotenv()

central_db_config = {
    "server": os.getenv("CENTRAL_DB_SERVER"),
    "database": os.getenv("CENTRAL_DB_DATABASE"),
    "username": os.getenv("CENTRAL_DB_USER"),
    "password": os.getenv("CENTRAL_DB_PASS")
}

def obter_ip_filial(filial):
    if 1 <= filial <= 200 or filial == 241:
        ip = f"10.16.{filial}.24"
    elif 201 <= filial <= 299:
        ip = f"10.17.{filial % 100}.24"
    elif 300 <= filial <= 399:
        ip = f"10.17.1{filial % 100}.24"
    elif 400 <= filial <= 499:
        ip = f"10.18.{filial % 100}.24"
    elif filial == 247:
        ip = f"192.168.201.1"
    else:
        raise ValueError("Número de filial inválido.")

    filial_db_config = {
        "server": ip,
        "database": os.getenv("FILIAL_DB_DATABASE"),
        "username": os.getenv("FILIAL_DB_USER"),
        "password": os.getenv("FILIAL_DB_PASS")
    }

    return filial_db_config

def conectar_filial(num_filial):
    config_bd_filial = obter_ip_filial(num_filial)
    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};"
            f"SERVER={config_bd_filial['server']};"
            f"DATABASE={config_bd_filial['database']};"
            f"UID={config_bd_filial['username']};"
            f"PWD={config_bd_filial['password']}"
        )
        return conn
    except Exception as e:
        log(f"Erro ao conectar ao banco da filial: {e}")
        return None

def conectar_central():
    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};"
            f"SERVER={central_db_config['server']};"
            f"DATABASE={central_db_config['database']};"
            f"UID={central_db_config['username']};"
            f"PWD={central_db_config['password']}"
        )
        return conn
    except Exception as e:
        log(f"Erro ao conectar ao banco central: {e}")
        return None

def ler_arquivo(nome_arquivo):
    if os.path.exists(nome_arquivo):
        with open(nome_arquivo, "r") as arquivo:
            return [linha.strip() for linha in arquivo.readlines() if linha.strip()]
    return []

def consultar_notas_central(chaves, num_filial):
    try:
        conn = conectar_central()
        if conn is None:
            return []

        cursor = conn.cursor()

        notas_na_central = []
        notas_nao_central = []
        notas_sem_pedido = []
        notas_outra_filial = []

        for chave in chaves:
            cursor.execute("SELECT NF_COMPRA, PEDIDO_COMPRA, EMPRESA FROM NF_COMPRA WHERE CHAVE_NFE = ?", (chave,))
            resultado = cursor.fetchone()

            if resultado:
                nf_compra, pedido_compra, empresa = resultado
                nota_info = {"CHAVE": chave, "EMPRESA": empresa}

                if pedido_compra is None:
                    notas_sem_pedido.append(chave)

                if nota_info["EMPRESA"] == num_filial:
                    notas_na_central.append(chave)
                else:
                    notas_outra_filial.append(nota_info)
            else:
                notas_nao_central.append(chave)

        cursor.close()
        conn.close()

        return notas_na_central, notas_nao_central, notas_sem_pedido, notas_outra_filial

    except Exception as e:
        log(f"Erro ao consultar notas na central: {e}")
        return [], [], [], []

def consultar_notas_filial(notas_na_central, num_filial):
    try:
        conn_filial = conectar_filial(num_filial)
        if conn_filial is None:
            return

        cursor = conn_filial.cursor()

        notas_integradas = []
        notas_nao_loja = []

        for chave in notas_na_central:
            cursor.execute("SELECT NF_COMPRA FROM NF_COMPRA WHERE CHAVE_NFE = ?", (chave,))
            resultado = cursor.fetchone()

            if resultado:
                notas_integradas.append(chave)
            else:
                notas_nao_loja.append(chave)

        cursor.close()
        conn_filial.close()

        return notas_integradas, notas_nao_loja
    except Exception as e:
        log(f"Erro ao consultar notas na filial: {e}")

def interagir_chamado(cod_chamado, token, notas_nao_central, notas_sem_pedido, notas_integradas, notas_nao_loja, notas_outra_filial):
    descricao = "Resumo da Integração de Notas\n\n"

    if notas_integradas:
        descricao += "*Notas Integradas na Filial:*\n" + "\n".join(notas_integradas) + "\n\n"

    if notas_nao_loja:
        descricao += "*Notas não encontradas na Loja:*\n" + "\n".join(notas_nao_loja) + "\n\n"

    if notas_sem_pedido:
        descricao += "*Notas sem Pedido de Compra:*\n" + "\n".join(notas_sem_pedido) + "\n\n"
        descricao += "Favor abrir um chamado com o assunto CSN - PEDIDO COMPLEMENTAR para as notas sem pedido de compra.\n\n"

    if notas_nao_central:
        descricao += "*Notas não encontradas na Central:*\n" + "\n".join(notas_nao_central) + "\n\n"
        descricao += "Chamado encaminhado para análise.\n\n"

    if notas_outra_filial:
        descricao += "*As seguintes notas não pertencem a esta loja:*\n"
        for nota in notas_outra_filial:
            descricao += f"{nota['CHAVE']} --  FILIAL {nota['EMPRESA']}\n"
        descricao += "\n"

    if notas_nao_central or notas_nao_loja:
        cod_status = "0000006"
    else:
        cod_status = "0000002"

    data_interacao = datetime.now().strftime("%d-%m-%Y")
    url = "https://api.desk.ms/ChamadosSuporte/interagir"

    payload = {
        "Chave": cod_chamado,
        "TChamado": {
            "CodFormaAtendimento": "1",
            "CodStatus": cod_status,
            "CodAprovador": [""],
            "TransferirOperador": "",
            "TransferirGrupo": "",
            "CodTerceiros": "",
            "Protocolo": "",
            "Descricao": descricao,
            "CodAgendamento": "",
            "DataAgendamento": "",
            "HoraAgendamento": "",
            "CodCausa": "000467",
            "CodOperador": "249",
            "CodGrupo": "",
            "EnviarEmail": "S",
            "EnvBase": "N",
            "CodFPMsg": "",
            "DataInteracao": data_interacao,
            "HoraInicial": "",
            "HoraFinal": "",
            "SMS": "",
            "ObservacaoInterna": "",
            "PrimeiroAtendimento": "S",
            "SegundoAtendimento": "N"
        },
        "TIc": {
            "Chave": {
                "278": "on",
                "280": "on"
            }
        }
    }

    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.put(url, json=payload, headers=headers)

        if response.status_code == 200:
            if cod_status == "0000006":
                log(f"Chamado {cod_chamado} encaminhado para análise.")
                log(response.text)
                log('\n')
            if cod_status == "0000002":
                log(f"Chamado {cod_chamado} encerrado com sucesso!")
                log(response.text)
                log('\n')
        else:
            log(f"Erro ao interagir no chamado. Código: {response.status_code}")
            log("Resposta da API:")
            log(response.text)
            try:
                erro_json = response.json()
                log(f"Detalhes do erro: {erro_json}")
            except ValueError:
                log("Não foi possível converter a resposta da API para JSON.")

    except requests.exceptions.RequestException as e:
        log(f"Erro ao conectar com a API: {e}")
