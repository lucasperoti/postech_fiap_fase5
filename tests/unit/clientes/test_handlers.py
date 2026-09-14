import json
import os

import boto3
import pytest

from clientes.handlers import criar_cliente, excluir_cliente

CPF_VALIDO = "529.982.247-25"


def _evento(body: dict, claims=None):
    evento = {"body": json.dumps(body), "requestContext": {}}
    if claims:
        evento["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}
    return evento


@pytest.fixture()
def clientes_tabela(aws_mock, env_vars, tabelas):
    kms = boto3.client("kms", region_name="us-east-1")
    chave = kms.create_key(Description="teste")["KeyMetadata"]["Arn"]
    os.environ["KMS_KEY_ID"] = chave
    return tabelas[os.environ["CLIENTES_TABLE"]]


def test_criar_cliente_com_sucesso(clientes_tabela):
    resposta = criar_cliente(
        _evento({"nome": "Ana", "email": "ana@email.com", "cpf": CPF_VALIDO}), None
    )
    assert resposta["statusCode"] == 201
    corpo = json.loads(resposta["body"])
    assert corpo["mascara_cpf"] == "***.***.***-25"
    assert "529" not in json.dumps(corpo)
    item = clientes_tabela.get_item(Key={"PK": f"CLIENTE#{corpo['id']}"})["Item"]
    assert item["cpf_enc"] != "52998224725"  # cifrado, nunca em claro


def test_criar_cliente_cpf_invalido(clientes_tabela):
    resposta = criar_cliente(_evento({"nome": "Ana", "email": "a@b.com", "cpf": "123"}), None)
    assert resposta["statusCode"] == 422


def test_criar_cliente_email_invalido(clientes_tabela):
    resposta = criar_cliente(
        _evento({"nome": "Ana", "email": "nao-email", "cpf": CPF_VALIDO}), None
    )
    assert resposta["statusCode"] == 422


def test_criar_cliente_nome_obrigatorio(clientes_tabela):
    resposta = criar_cliente(_evento({"email": "a@b.com", "cpf": CPF_VALIDO}), None)
    assert resposta["statusCode"] == 422


def test_excluir_cliente_apaga_cpf(clientes_tabela):
    resposta = criar_cliente(_evento({"nome": "Ana", "email": "a@b.com", "cpf": CPF_VALIDO}), None)
    cliente_id = json.loads(resposta["body"])["id"]
    clientes_tabela.update_item(
        Key={"PK": f"CLIENTE#{cliente_id}"},
        UpdateExpression="SET cognito_sub = :sub",
        ExpressionAttributeValues={":sub": "sub-1"},
    )
    resposta = excluir_cliente(_evento({}, claims={"sub": "sub-1"}), None)
    assert resposta["statusCode"] == 200
    item = clientes_tabela.get_item(Key={"PK": f"CLIENTE#{cliente_id}"})["Item"]
    assert item["status"] == "EXCLUIDO"
    assert "cpf_enc" not in item
    assert "endereco_enc" not in item


def test_excluir_cliente_sem_autenticacao(clientes_tabela):
    resposta = excluir_cliente(_evento({}), None)
    assert resposta["statusCode"] == 401
