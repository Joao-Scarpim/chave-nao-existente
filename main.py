import requests
import re
import functions as fun


url = "https://api.desk.ms/Login/autenticar"

headers = {
    "Authorization": "30c55b0282a7962061dd41a654b6610d02635ddf",
    "JsonPath": "true"
}

payload = {
    "PublicKey": "1bb099a1915916de10c9be05ff4d2cafed607e7f"
}

try:
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        response_data = response.json()
        token = response_data["access_token"]
        print(f"Autenticação realizada com sucesso! Token: {token}")

    else:
        print(f"Erro na autenticação. Código: {response.status_code}")
        print(f"Mensagem: {response.text}")

except Exception as e:
    print(f"Ocorreu um erro durante a autenticação: {e}")















url = "https://api.desk.ms/ChamadosSuporte/lista"

headers = {
    "Authorization" : f"{token}"
}

payload = {
  "Pesquisa":"CSN - CHAVE NAO EXISTENTE NO BANCO DE DADOS",
  "Tatual":"",
  "Ativo":"000001",
  "StatusSLA":"",
  "Colunas":
  {
	"Chave":"on",
	"CodChamado":"on",
	"NomePrioridade":"on",
	"DataCriacao":"on",
	"HoraCriacao":"on",
	"DataFinalizacao":"on",
	"HoraFinalizacao":"on",
	"DataAlteracao":"on",
	"HoraAlteracao":"on",
	"NomeStatus":"on",
	"Assunto":"on",
	"Descricao":"on",
	"ChaveUsuario":"on",
	"NomeUsuario":"on",
	"SobrenomeUsuario":"on",
  "NomeCompletoSolicitante":"on",
	"SolicitanteEmail":"on",
	"NomeOperador":"on",
	"SobrenomeOperador":"on",
	"TotalAcoes":"on",
	"TotalAnexos":"on",
	"Sla":"on",
	"CodGrupo":"on",
	"NomeGrupo":"on",
	"CodSolicitacao":"on",
	"CodSubCategoria":"on",
	"CodTipoOcorrencia":"on",
	"CodCategoriaTipo":"on",
	"CodPrioridadeAtual":"on",
	"CodStatusAtual":"on",
	"_6313":"on"
  },
  "Ordem": [
    {
      "Coluna": "Chave",
      "Direcao": "true"
    }
  ]
}




try:
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        response_data = response.json()
        chamados = response_data["root"]

    for chamado in chamados:


        # ---------extraindo as chaves da descrição e adicionando ao txt
        chaves = chamado["Descricao"]
        padrao = r"\b\d{44}\b"
        chaves_nf = re.findall(padrao, chaves)


        # ---------------------------------------------------

        # ----------conseguir o número da filial
        regex_filial = r"\d+"
        filial = chamado["NomeUsuario"]
        cod_chamado = chamado["CodChamado"]
        print(cod_chamado)
        match = re.search(regex_filial, filial)
        if match:
            num_filial = int(match.group())
        print(num_filial)


        # -------consultar cada nota na central
        notas_confirmadas,  notas_nao_central, notas_sem_pedido, notas_outra_filial = fun.consultar_notas_central(chaves_nf, num_filial)

        # --------integrar as notas na central ----------
        notas_integradas, notas_nao_loja = fun.consultar_notas_filial(notas_confirmadas, num_filial)

        # --------encerrar chamado---------
        fun.interagir_chamado(cod_chamado, token, notas_nao_central, notas_sem_pedido, notas_integradas, notas_nao_loja, notas_outra_filial)


    else:
        print(f"Erro na requisição. Código: {response.status_code}")
        print(f"Mensagem: {response.text}")

except Exception as e:
    print(f"Ocorreu um erro durante a requisição: {e}")
