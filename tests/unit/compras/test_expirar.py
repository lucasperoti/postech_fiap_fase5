import os
import time
from unittest import mock

import pytest

from compras.expirar import expirar_reservas


@pytest.fixture()
def base(aws_mock, env_vars, tabelas):
    os.environ["SAGA_ARN"] = "arn:aws:states:us-east-1:000000000000:stateMachine:teste"
    compras = tabelas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={
            "PK": "COMPRA#velha",
            "cliente_id": "c1",
            "veiculo_id": "v1",
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": "PAG-1",
            "task_token": "token-v",
            "reservado_ts": int(time.time()) - 3600,
        }
    )
    compras.put_item(
        Item={
            "PK": "COMPRA#nova",
            "cliente_id": "c1",
            "veiculo_id": "v2",
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": "PAG-2",
            "reservado_ts": int(time.time()),
        }
    )
    veiculos = tabelas[os.environ["VEICULOS_TABLE"]]
    for vid in ("v1", "v2"):
        veiculos.put_item(
            Item={
                "PK": f"VEICULO#{vid}",
                "preco_centavos": 100,
                "status": "RESERVADO",
                "GSI1PK": "STATUS#RESERVADO",
                "GSI1SK": f"PRECO#00000000000100#{vid}",
            }
        )
    return tabelas


def test_expira_somente_reservas_velhas(base):
    cliente = mock.MagicMock()
    with mock.patch("compras.expirar.cliente_aws", return_value=cliente):
        resposta = expirar_reservas({}, None)
    assert resposta["expiradas"] == 1
    compras = base[os.environ["COMPRAS_TABLE"]]
    assert compras.get_item(Key={"PK": "COMPRA#velha"})["Item"]["estado"] == "CANCELADA"
    assert compras.get_item(Key={"PK": "COMPRA#velha"})["Item"]["motivo_cancelamento"] == "EXPIRADA"
    assert compras.get_item(Key={"PK": "COMPRA#nova"})["Item"]["estado"] == "AGUARDANDO_PAGAMENTO"
    assert base[os.environ["VEICULOS_TABLE"]].get_item(Key={"PK": "VEICULO#v1"})["Item"]["status"] == "DISPONIVEL"
    cliente.send_task_failure.assert_called_once()
