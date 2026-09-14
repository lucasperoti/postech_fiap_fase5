import os
import time

import pytest

from compras.atividades import aguardar_pagamento, confirmar_venda, liberar_reserva


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
            "reservado_ts": int(time.time()),
        }
    )
    return tabelas


def _seed_veiculo(veiculos, vid="v1"):
    veiculos.put_item(
        Item={
            "PK": f"VEICULO#{vid}",
            "preco_centavos": 100,
            "status": "RESERVADO",
            "GSI1PK": "STATUS#RESERVADO",
            "GSI1SK": f"PRECO#00000000000100#{vid}",
        }
    )


def test_aguardar_pagamento_grava_task_token(base):
    resposta = aguardar_pagamento({"compra_id": "k1", "taskToken": "token-abc"}, None)
    assert resposta["ok"] is True
    item = base[os.environ["COMPRAS_TABLE"]].get_item(Key={"PK": "COMPRA#k1"})["Item"]
    assert item["task_token"] == "token-abc"


def test_confirmar_venda_atividade(base):
    _seed_veiculo(base[os.environ["VEICULOS_TABLE"]])
    resposta = confirmar_venda({"compra_id": "k1"}, None)
    assert resposta["resultado"] == "VENDIDO"
    assert base[os.environ["COMPRAS_TABLE"]].get_item(Key={"PK": "COMPRA#k1"})["Item"]["estado"] == "PAGO"


def test_liberar_reserva_atividade(base):
    _seed_veiculo(base[os.environ["VEICULOS_TABLE"]])
    resposta = liberar_reserva({"compra_id": "k1", "motivo": "PAGAMENTO_RECUSADO"}, None)
    assert resposta["resultado"] == "CANCELADA"
    assert base[os.environ["COMPRAS_TABLE"]].get_item(Key={"PK": "COMPRA#k1"})["Item"]["estado"] == "CANCELADA"
