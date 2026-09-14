import json
import os
import time
import uuid

from botocore.exceptions import ClientError

from compras.servico import (
    VeiculoIndisponivel,
    cancelar_compra,
    gerar_codigo_pagamento,
    reservar_veiculo,
)
from shared.auth import resolver_cliente_id
from shared.aws import cliente_aws
from shared.db import tabela
from shared.responses import created, error, ok


def iniciar_compra(event, context):
    compras = tabela("COMPRAS_TABLE")
    cliente_id, erro = resolver_cliente_id(event, tabela("CLIENTES_TABLE"))
    if erro:
        return erro
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error(400, "JSON_INVALIDO", "Corpo da requisição não é um JSON válido")
    veiculo_id = dados.get("veiculo_id")
    if not veiculo_id:
        return error(422, "VALIDACAO", "veiculo_id é obrigatório")

    compra_id = str(uuid.uuid4())
    try:
        reservar_veiculo(veiculo_id, compra_id)
    except VeiculoIndisponivel:
        return error(409, "VEICULO_INDISPONIVEL", "Veículo já reservado ou vendido")

    codigo = gerar_codigo_pagamento()
    compras.put_item(
        Item={
            "PK": f"COMPRA#{compra_id}",
            "cliente_id": cliente_id,
            "veiculo_id": veiculo_id,
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": codigo,
            "reservado_ts": int(time.time()),
            "criado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    try:
        cliente_aws("stepfunctions").start_execution(
            stateMachineArn=os.environ["SAGA_ARN"],
            name=compra_id,
            input=json.dumps({"compra_id": compra_id}),
        )
    except ClientError:
        cancelar_compra(compra_id, "ERRO_ORQUESTRADOR")
        return error(500, "ERRO_ORQUESTRADOR", "Não foi possível iniciar o processo de pagamento")
    return created(
        {
            "compra_id": compra_id,
            "veiculo_id": veiculo_id,
            "estado": "AGUARDANDO_PAGAMENTO",
            "codigo_pagamento": codigo,
        }
    )


def retirar_veiculo(event, context):
    compras = tabela("COMPRAS_TABLE")
    cliente_id, erro = resolver_cliente_id(event, tabela("CLIENTES_TABLE"))
    if erro:
        return erro
    compra_id = event.get("pathParameters", {}).get("id")
    compra = compras.get_item(Key={"PK": f"COMPRA#{compra_id}"}).get("Item")
    if not compra:
        return error(404, "NAO_ENCONTRADO", "Compra não encontrada")
    if compra["cliente_id"] != cliente_id:
        return error(403, "ACESSO_NEGADO", "Esta compra pertence a outro cliente")
    try:
        compras.update_item(
            Key={"PK": f"COMPRA#{compra_id}"},
            ConditionExpression="estado = :pago",
            UpdateExpression="SET estado = :concluida, concluida_em = :agora",
            ExpressionAttributeValues={
                ":pago": "PAGO",
                ":concluida": "CONCLUIDA",
                ":agora": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error(409, "ESTADO_INVALIDO", "A compra precisa estar PAGO para retirada")
        raise
    return ok({"compra_id": compra_id, "estado": "CONCLUIDA"})
