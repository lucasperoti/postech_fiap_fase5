import json
import os
from unittest import mock

import boto3
import pytest
from botocore.exceptions import ClientError

from clientes.handlers import criar_cliente


def _evento(body):
    return {"body": json.dumps(body), "requestContext": {}}


@pytest.fixture()
def clientes_tabela(aws_mock, env_vars, tabelas):
    kms = boto3.client("kms", region_name="us-east-1")
    os.environ["KMS_KEY_ID"] = kms.create_key(Description="teste")["KeyMetadata"]["Arn"]
    os.environ["USER_POOL_ID"] = "us-east-1_poolteste"
    return tabelas[os.environ["CLIENTES_TABLE"]]


def _cognito_mock(sub="sub-123"):
    cliente = mock.MagicMock()
    cliente.admin_create_user.return_value = {
        "User": {"Attributes": [{"Name": "sub", "Value": sub}]}
    }
    return cliente


def test_registro_cria_usuario_cognito_e_grava_sub(clientes_tabela):
    with mock.patch("clientes.handlers.cliente_aws", return_value=_cognito_mock()):
        resposta = criar_cliente(
            _evento(
                {
                    "nome": "Ana",
                    "email": "ana@email.com",
                    "cpf": "529.982.247-25",
                    "senha": "SenhaForte123!",
                }
            ),
            None,
        )
    assert resposta["statusCode"] == 201
    cliente_id = json.loads(resposta["body"])["id"]
    item = clientes_tabela.get_item(Key={"PK": f"CLIENTE#{cliente_id}"})["Item"]
    assert item["cognito_sub"] == "sub-123"


def test_registro_sem_senha_quando_auth_desabilitado(clientes_tabela):
    os.environ.pop("USER_POOL_ID", None)
    resposta = criar_cliente(
        _evento({"nome": "Ana", "email": "ana@email.com", "cpf": "529.982.247-25"}), None
    )
    assert resposta["statusCode"] == 201


def test_registro_conflito_quando_usuario_ja_existe(clientes_tabela):
    cliente = _cognito_mock()
    cliente.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "UsernameExistsException"}}, "AdminCreateUser"
    )
    with mock.patch("clientes.handlers.cliente_aws", return_value=cliente):
        resposta = criar_cliente(
            _evento(
                {
                    "nome": "Ana",
                    "email": "ana@email.com",
                    "cpf": "529.982.247-25",
                    "senha": "SenhaForte123!",
                }
            ),
            None,
        )
    assert resposta["statusCode"] == 409
