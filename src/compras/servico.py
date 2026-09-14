import secrets
import time

from botocore.exceptions import ClientError

from shared.db import tabela


class VeiculoIndisponivel(Exception):
    pass


def gerar_codigo_pagamento() -> str:
    return "PAG-" + secrets.token_hex(10).upper()


def reservar_veiculo(veiculo_id: str, compra_id: str) -> None:
    veiculos = tabela("VEICULOS_TABLE")
    try:
        veiculos.update_item(
            Key={"PK": f"VEICULO#{veiculo_id}"},
            ConditionExpression="#s = :disponivel",
            UpdateExpression="SET #s = :reservado, reservado_por = :compra, reservado_ts = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":disponivel": "DISPONIVEL",
                ":reservado": "RESERVADO",
                ":compra": compra_id,
                ":ts": int(time.time()),
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise VeiculoIndisponivel(veiculo_id) from exc
        raise


def confirmar_venda(compra_id: str) -> None:
    compras = tabela("COMPRAS_TABLE")
    compra = compras.get_item(Key={"PK": f"COMPRA#{compra_id}"}).get("Item")
    if not compra:
        raise RuntimeError(f"Compra {compra_id} não encontrada")
    agora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    compras.update_item(
        Key={"PK": f"COMPRA#{compra_id}"},
        ConditionExpression="estado = :aguardando",
        UpdateExpression="SET estado = :pago, pago_em = :agora",
        ExpressionAttributeValues={
            ":aguardando": "AGUARDANDO_PAGAMENTO",
            ":pago": "PAGO",
            ":agora": agora,
        },
    )
    veiculos = tabela("VEICULOS_TABLE")
    veiculo_id = compra["veiculo_id"]
    veiculos.update_item(
        Key={"PK": f"VEICULO#{veiculo_id}"},
        ConditionExpression="#s = :reservado",
        UpdateExpression="SET #s = :vendido, vendido_em = :agora, GSI1PK = :gsi",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":reservado": "RESERVADO",
            ":vendido": "VENDIDO",
            ":agora": agora,
            ":gsi": "STATUS#VENDIDO",
        },
    )


def cancelar_compra(compra_id: str, motivo: str) -> None:
    compras = tabela("COMPRAS_TABLE")
    chave = {"PK": f"COMPRA#{compra_id}"}
    compra = compras.get_item(Key=chave).get("Item")
    if not compra or compra.get("estado") in ("CANCELADA", "CONCLUIDA"):
        return  # idempotente
    veiculos = tabela("VEICULOS_TABLE")
    try:
        veiculos.update_item(
            Key={"PK": f"VEICULO#{compra['veiculo_id']}"},
            ConditionExpression="#s = :reservado",
            UpdateExpression="SET #s = :disponivel, GSI1PK = :gsi REMOVE reservado_por, reservado_ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":reservado": "RESERVADO",
                ":disponivel": "DISPONIVEL",
                ":gsi": "STATUS#DISPONIVEL",
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
    try:
        compras.update_item(
            Key=chave,
            ConditionExpression="estado = :aguardando",
            UpdateExpression="SET estado = :cancelada, motivo_cancelamento = :motivo, cancelada_em = :agora",
            ExpressionAttributeValues={
                ":aguardando": "AGUARDANDO_PAGAMENTO",
                ":cancelada": "CANCELADA",
                ":motivo": motivo,
                ":agora": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
