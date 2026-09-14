import json
import os
import uuid

import pytest

from veiculos.handlers import chave_ordenacao, criar_veiculo, editar_veiculo, listar_veiculos

EVENTO_ADMIN = {"requestContext": {}, "headers": {"x-admin": "true"}}


def _evento_criar(**campos):
    base = {"marca": "Fiat", "modelo": "Uno", "ano": 2020, "cor": "branco", "preco": 35000.0}
    base.update(campos)
    return {"body": json.dumps(base), **EVENTO_ADMIN}


@pytest.fixture()
def veiculos_tabela(aws_mock, env_vars, tabelas):
    return tabelas[os.environ["VEICULOS_TABLE"]]


def _criar(evento, tabela):
    resposta = criar_veiculo(evento, None)
    assert resposta["statusCode"] == 201, resposta["body"]
    return json.loads(resposta["body"])


def test_criar_veiculo(veiculos_tabela):
    corpo = _criar(_evento_criar(), veiculos_tabela)
    assert corpo["status"] == "DISPONIVEL"
    item = veiculos_tabela.get_item(Key={"PK": f"VEICULO#{corpo['id']}"})["Item"]
    assert item["preco_centavos"] == 3500000
    assert item["GSI1PK"] == "STATUS#DISPONIVEL"


def test_criar_veiculo_sem_admin(veiculos_tabela):
    resposta = criar_veiculo({**_evento_criar(), "headers": {}}, None)
    assert resposta["statusCode"] == 403


def test_criar_veiculo_preco_negativo(veiculos_tabela):
    resposta = criar_veiculo(_evento_criar(preco=-1), None)
    assert resposta["statusCode"] == 422


def test_listar_ordenado_por_preco(veiculos_tabela):
    _criar(_evento_criar(modelo="Caro", preco=145000.0), veiculos_tabela)
    _criar(_evento_criar(modelo="Barato", preco=20000.0), veiculos_tabela)
    _criar(_evento_criar(modelo="Meio", preco=52000.0), veiculos_tabela)
    resposta = listar_veiculos({"queryStringParameters": {}}, None)
    corpo = json.loads(resposta["body"])
    precos = [v["preco"] for v in corpo["veiculos"]]
    assert all(isinstance(p, float) for p in precos)
    assert precos == sorted(precos)
    assert [v["modelo"] for v in corpo["veiculos"]] == ["Barato", "Meio", "Caro"]


def test_listar_vendidos(veiculos_tabela):
    corpo = _criar(_evento_criar(), veiculos_tabela)
    veiculos_tabela.update_item(
        Key={"PK": f"VEICULO#{corpo['id']}"},
        UpdateExpression="SET #s = :s, GSI1PK = :g",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "VENDIDO", ":g": "STATUS#VENDIDO"},
    )
    resposta = listar_veiculos({"queryStringParameters": {"status": "VENDIDO"}}, None)
    corpo_lista = json.loads(resposta["body"])
    assert len(corpo_lista["veiculos"]) == 1


def test_listar_status_invalido(veiculos_tabela):
    resposta = listar_veiculos({"queryStringParameters": {"status": "RESERVADO"}}, None)
    assert resposta["statusCode"] == 422


def test_editar_veiculo_atualiza_preco_e_gsi(veiculos_tabela):
    corpo = _criar(_evento_criar(preco=30000.0), veiculos_tabela)
    evento = {
        "pathParameters": {"id": corpo["id"]},
        "body": json.dumps({"preco": 31000.0, "cor": "prata"}),
        **EVENTO_ADMIN,
    }
    resposta = editar_veiculo(evento, None)
    assert resposta["statusCode"] == 200
    item = veiculos_tabela.get_item(Key={"PK": f"VEICULO#{corpo['id']}"})["Item"]
    assert item["preco_centavos"] == 3100000
    assert item["cor"] == "prata"
    assert item["GSI1SK"].startswith("PRECO#00000003100000")


def test_editar_veiculo_nao_encontrado(veiculos_tabela):
    evento = {
        "pathParameters": {"id": str(uuid.uuid4())},
        "body": json.dumps({"cor": "prata"}),
        **EVENTO_ADMIN,
    }
    assert editar_veiculo(evento, None)["statusCode"] == 404


def test_chave_ordenacao_zero_padding():
    assert chave_ordenacao(3500000, "abc") == "PRECO#00000003500000#abc"
