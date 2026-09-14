import json
import os
import time
from unittest import mock

import pytest
from botocore.exceptions import ClientError

from compras.handlers import iniciar_compra, retirar_veiculo
from compras.servico import (
    VeiculoIndisponivel,
    cancelar_compra,
    confirmar_venda,
    gerar_codigo_pagamento,
    reservar_veiculo,
)


@pytest.fixture()
def tabelas_prontas(aws_mock, env_vars, tabelas):
    os.environ["SAGA_ARN"] = "arn:aws:states:us-east-1:000000000000:stateMachine:teste"
    return tabelas


def _seed_veiculo(veiculos, status="DISPONIVEL"):
    vid = "v1"
    veiculos.put_item(
        Item={
            "PK": f"VEICULO#{vid}",
            "marca": "Fiat",
            "modelo": "Uno",
            "ano": 2020,
            "cor": "branco",
            "preco_centavos": 3500000,
            "status": status,
            "GSI1PK": f"STATUS#{status}",
            "GSI1SK": f"PRECO#00000003500000#{vid}",
        }
    )
    return vid


def _evento_compra(veiculo_id, cliente_id="c1"):
    return {
        "body": json.dumps({"veiculo_id": veiculo_id}),
        "requestContext": {},
        "headers": {"x-cliente-id": cliente_id},
    }


def test_gerar_codigo_pagamento_formato():
    codigo = gerar_codigo_pagamento()
    assert codigo.startswith("PAG-")
    assert len(codigo) == 24


def test_reservar_veiculo_sucesso(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]])
    reservar_veiculo(vid, "compra-1")
    item = tabelas_prontas[os.environ["VEICULOS_TABLE"]].get_item(Key={"PK": f"VEICULO#{vid}"})["Item"]
    assert item["status"] == "RESERVADO"


def test_reservar_veiculo_duplicada_levanta(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]])
    reservar_veiculo(vid, "compra-1")
    with pytest.raises(VeiculoIndisponivel):
        reservar_veiculo(vid, "compra-2")


def test_iniciar_compra_sucesso(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]])
    with mock.patch("compras.handlers.cliente_aws") as cliente:
        resposta = iniciar_compra(_evento_compra(vid), None)
    assert resposta["statusCode"] == 201, resposta["body"]
    corpo = json.loads(resposta["body"])
    assert corpo["codigo_pagamento"].startswith("PAG-")
    assert corpo["estado"] == "AGUARDANDO_PAGAMENTO"
    cliente.assert_called_once_with("stepfunctions")
    cliente.return_value.start_execution.assert_called_once()


def test_iniciar_compra_veiculo_indisponivel_409(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]], status="VENDIDO")
    with mock.patch("compras.handlers.cliente_aws"):
        resposta = iniciar_compra(_evento_compra(vid), None)
    assert resposta["statusCode"] == 409


def test_iniciar_compra_falha_na_saga_compensa(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]])
    erro = ClientError({"Error": {"Code": "StateMachineDoesNotExist"}}, "StartExecution")
    with mock.patch("compras.handlers.cliente_aws") as cliente:
        cliente.return_value.start_execution.side_effect = erro
        resposta = iniciar_compra(_evento_compra(vid), None)
    assert resposta["statusCode"] == 500
    item = tabelas_prontas[os.environ["VEICULOS_TABLE"]].get_item(Key={"PK": f"VEICULO#{vid}"})["Item"]
    assert item["status"] == "DISPONIVEL"  # reserva compensada


def test_confirmar_venda(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]], status="RESERVADO")
    compras = tabelas_prontas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={
            "PK": "COMPRA#k1",
            "cliente_id": "c1",
            "veiculo_id": vid,
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": "PAG-X",
            "reservado_ts": int(time.time()),
        }
    )
    confirmar_venda("k1")
    assert compras.get_item(Key={"PK": "COMPRA#k1"})["Item"]["estado"] == "PAGO"
    veiculo = tabelas_prontas[os.environ["VEICULOS_TABLE"]].get_item(Key={"PK": f"VEICULO#{vid}"})["Item"]
    assert veiculo["status"] == "VENDIDO"
    assert veiculo["GSI1PK"] == "STATUS#VENDIDO"


def test_cancelar_compra_libera_veiculo(tabelas_prontas):
    vid = _seed_veiculo(tabelas_prontas[os.environ["VEICULOS_TABLE"]], status="RESERVADO")
    compras = tabelas_prontas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={
            "PK": "COMPRA#k2",
            "cliente_id": "c1",
            "veiculo_id": vid,
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": "PAG-Y",
            "reservado_ts": int(time.time()),
        }
    )
    cancelar_compra("k2", "EXPIRADA")
    compra = compras.get_item(Key={"PK": "COMPRA#k2"})["Item"]
    assert compra["estado"] == "CANCELADA"
    assert compra["motivo_cancelamento"] == "EXPIRADA"
    veiculo = tabelas_prontas[os.environ["VEICULOS_TABLE"]].get_item(Key={"PK": f"VEICULO#{vid}"})["Item"]
    assert veiculo["status"] == "DISPONIVEL"


def test_retirar_veiculo_sucesso(tabelas_prontas):
    compras = tabelas_prontas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={"PK": "COMPRA#k3", "cliente_id": "c1", "veiculo_id": "v9", "estado": "PAGO"}
    )
    evento = {
        "pathParameters": {"id": "k3"},
        "requestContext": {},
        "headers": {"x-cliente-id": "c1"},
    }
    resposta = retirar_veiculo(evento, None)
    assert resposta["statusCode"] == 200
    assert compras.get_item(Key={"PK": "COMPRA#k3"})["Item"]["estado"] == "CONCLUIDA"


def test_retirar_veiculo_de_outro_cliente_403(tabelas_prontas):
    compras = tabelas_prontas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={"PK": "COMPRA#k4", "cliente_id": "c1", "veiculo_id": "v9", "estado": "PAGO"}
    )
    evento = {
        "pathParameters": {"id": "k4"},
        "requestContext": {},
        "headers": {"x-cliente-id": "c2"},
    }
    assert retirar_veiculo(evento, None)["statusCode"] == 403


def test_retirar_veiculo_nao_pago_409(tabelas_prontas):
    compras = tabelas_prontas[os.environ["COMPRAS_TABLE"]]
    compras.put_item(
        Item={
            "PK": "COMPRA#k5",
            "cliente_id": "c1",
            "veiculo_id": "v9",
            "estado": "AGUARDANDO_PAGAMENTO",
        }
    )
    evento = {
        "pathParameters": {"id": "k5"},
        "requestContext": {},
        "headers": {"x-cliente-id": "c1"},
    }
    assert retirar_veiculo(evento, None)["statusCode"] == 409
