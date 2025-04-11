import pyodbc
import os
import requests
from dotenv import load_dotenv
from datetime import datetime


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
    """Estabelece conexão com o banco de dados central e retorna a conexão."""

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
        print(f"Erro ao conectar ao banco da filial: {e}")
        return None



def conectar_central():
    """Estabelece conexão com o banco de dados central e retorna a conexão."""
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
        print(f"Erro ao conectar ao banco central: {e}")
        return None




def ler_arquivo(nome_arquivo):
    """Lê um arquivo linha por linha e retorna uma lista de strings sem quebras de linha."""
    if os.path.exists(nome_arquivo):
        with open(nome_arquivo, "r") as arquivo:
            return [linha.strip() for linha in arquivo.readlines() if linha.strip()]
    return []

def consultar_notas_central(chaves, num_filial):
    """Consulta as notas no banco central e separa as chaves conforme sua situação."""
    try:
        conn = conectar_central()
        if conn is None:
            return []

        cursor = conn.cursor()

        notas_na_central = []
        notas_nao_central = []
        notas_sem_pedido = []
        notas_outra_filial =[]

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
                    notas_outra_filial.append(nota_info)  # Somente notas com pedido serão verificadas na filial
            else:
                notas_nao_central.append(chave)

        cursor.close()
        conn.close()


        return notas_na_central, notas_nao_central, notas_sem_pedido, notas_outra_filial  # Apenas as notas confirmadas na central serão verificadas na filial

    except Exception as e:
        print(f"Erro ao consultar notas na central: {e}")
        return [], [], []

def consultar_notas_filial(notas_na_central, num_filial):
    """Consulta apenas as notas já confirmadas na central no banco da filial."""
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
        print(f"Erro ao consultar notas na filial: {e}")


def interagir_chamado(cod_chamado, token, notas_nao_central, notas_sem_pedido, notas_integradas, notas_nao_loja, notas_outra_filial):
    """
    Interage em um chamado na API Desk.ms, atualizando a descrição com as notas extraídas.

    :param cod_chamado: Código do chamado a ser interagido.
    :param token: Token de autenticação na API.
    """

    # Criando a descrição formatada
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
        descricao += "*As seguintes notas não pertencem a esta loja:*\n" + "\n".join(notas_nao_central) + "\n\n"
        for nota in notas_outra_filial:
            descricao += f"{nota['CHAVE']} --  FILIAL {nota['EMPRESA']}\n"
        descricao += "\n"


    # Definição do status do chamado
    if notas_nao_central or notas_nao_loja:
        cod_status = "0000006"  # Chamado permanece aberto para análise
    else:
        cod_status = "0000002"  # Chamado pode ser encerrado

    # Obtendo data e hora atual
    data_interacao = datetime.now().strftime("%d-%m-%Y")

    # URL da API
    url = "https://api.desk.ms/ChamadosSuporte/interagir"

    # Payload da requisição
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

    # Configuração do cabeçalho da requisição
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.put(url, json=payload, headers=headers)

        if response.status_code == 200:
            print(f"Interação no chamado {cod_chamado} realizada com sucesso!")
            print(response.text)

        else:
            print(f"Erro ao interagir no chamado. Código: {response.status_code}")
            print("Resposta da API:")
            print(response.text)

            # Tenta extrair detalhes do erro se a resposta for JSON
            try:
                erro_json = response.json()
                print("Detalhes do erro:", erro_json)
            except ValueError:
                print("Não foi possível converter a resposta da API para JSON.")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao conectar com a API: {e}")


