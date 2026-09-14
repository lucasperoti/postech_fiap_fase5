import os
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
import pytest

from .conftest import cria_cliente, cria_veiculo

pytestmark = pytest.mark.e2e


def test_listagem_ordenada_por_preco(api, admin_headers):
    cria_veiculo(api, admin_headers, preco=145000.0, modelo="Caro")
    cria_veiculo(api, admin_headers, preco=20000.0, modelo="Barato")
    resposta = api.get("/veiculos", params={"status": "DISPONIVEL"})
    assert resposta.status_code == 200
    precos = [v["preco"] for v in resposta.json()["veiculos"]]
    assert all(isinstance(p, float) for p in precos)
    assert precos == sorted(precos)
    assert precos == [20000.0, 145000.0]


def test_fluxo_compra_retorna_codigo_de_pagamento(api, admin_headers):
    _, headers = cria_cliente(api)
    veiculo_id = cria_veiculo(api, admin_headers)
    resposta = api.post("/compras", json={"veiculo_id": veiculo_id}, headers=headers)
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["codigo_pagamento"].startswith("PAG-")
    assert corpo["estado"] == "AGUARDANDO_PAGAMENTO"


def test_concorrencia_duas_reservas_mesmo_veiculo(api, admin_headers):
    _, headers_a = cria_cliente(api, nome="Ana")
    _, headers_b = cria_cliente(api, nome="Bruno", cpf="111.444.777-35")
    veiculo_id = cria_veiculo(api, admin_headers)

    def reserva(headers):
        return api.post("/compras", json={"veiculo_id": veiculo_id}, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(reserva, [headers_a, headers_b]))

    status = sorted(r.status_code for r in resultados)
    assert status == [201, 409]


def test_expiracao_libera_veiculo(api, admin_headers, aws):
    _, headers = cria_cliente(api, nome="Carla")
    veiculo_id = cria_veiculo(api, admin_headers, modelo="Expiravel")
    resposta = api.post("/compras", json={"veiculo_id": veiculo_id}, headers=headers)
    compra_id = resposta.json()["compra_id"]

    aws.update_item(
        TableName="fase5-local-compras",
        Key={"PK": {"S": f"COMPRA#{compra_id}"}},
        UpdateExpression="SET reservado_ts = :ts",
        ExpressionAttributeValues={":ts": {"N": str(int(time.time()) - 3600)}},
    )
    lambda_client = boto3.client(
        "lambda",
        region_name="us-east-1",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    funcoes = lambda_client.list_functions()["Functions"]
    nome_expirar = next(f["FunctionName"] for f in funcoes if "ExpirarReservasFn" in f["FunctionName"])
    lambda_client.invoke(FunctionName=nome_expirar, InvocationType="RequestResponse")

    resposta = api.get("/veiculos", params={"status": "DISPONIVEL"})
    ids = [v["id"] for v in resposta.json()["veiculos"]]
    assert veiculo_id in ids  # compensação liberou o veículo
