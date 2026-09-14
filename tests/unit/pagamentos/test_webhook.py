import json
import os
import time
from unittest import mock

import pytest

from pagamentos.handlers import processar_webhook

SEGREDO = {"segredo": "segredo-super-secreto"}


@pytest.fixture()
def base(aws_mock, env_vars, tabelas):
    os.environ["SAGA_ARN"] = "arn:aws:states:us-east-1:000000000000:stateMachine:teste"
    compras = tabelas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={
            "PK": "COMPRA#k1",
            "cliente_id": "c1",
            "veiculo_id": "v1",
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": "PAG-X",
            "task_token": "token-1",
            "reservado_ts": int(time.time()),
        }
    )
    return tabelas


def _evento(compra_id="k1", resultado="APROVADO", segredo="segredo-super-secreto"):
    return {
        "body": json.dumps({"compra_id": compra_id, "resultado": resultado}),
        "headers": {"x-webhook-secret": segredo},
    }


def _mock_aws():
    cliente = mock.MagicMock()
    cliente.get_secret_value.return_value = {"SecretString": json.dumps(SEGREDO)}
    return cliente


def test_webhook_aprovado_envia_task_success(base):
    cliente = _mock_aws()
    with mock.patch("pagamentos.handlers.cliente_aws", return_value=cliente):
        resposta = processar_webhook(_evento(), None)
    assert resposta["statusCode"] == 200
    cliente.send_task_success.assert_called_once_with(
        taskToken="token-1",
        output=json.dumps({"compra_id": "k1", "resultado": "APROVADO"}),
    )


def test_webhook_segredo_invalido_401(base):
    with mock.patch("pagamentos.handlers.cliente_aws", return_value=_mock_aws()):
        resposta = processar_webhook(_evento(segredo="errado"), None)
    assert resposta["statusCode"] == 401


def test_webhook_compra_cancelada_409(base):
    base[os.environ["COMPRAS_TABLE"]].update_item(
        Key={"PK": "COMPRA#k1"},
        UpdateExpression="SET estado = :c",
        ExpressionAttributeValues={":c": "CANCELADA"},
    )
    with mock.patch("pagamentos.handlers.cliente_aws", return_value=_mock_aws()):
        resposta = processar_webhook(_evento(), None)
    assert resposta["statusCode"] == 409


def test_webhook_recusado_envia_task_failure(base):
    cliente = _mock_aws()
    with mock.patch("pagamentos.handlers.cliente_aws", return_value=cliente):
        resposta = processar_webhook(_evento(resultado="RECUSADO"), None)
    assert resposta["statusCode"] == 200
    cliente.send_task_failure.assert_called_once_with(taskToken="token-1", error="PAGAMENTO_RECUSADO")
