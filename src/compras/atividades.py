from compras import servico
from shared.db import tabela


def aguardar_pagamento(event, context):
    tabela("COMPRAS_TABLE").update_item(
        Key={"PK": f"COMPRA#{event['compra_id']}"},
        UpdateExpression="SET task_token = :token",
        ExpressionAttributeValues={":token": event["taskToken"]},
    )
    return {"ok": True}


def confirmar_venda(event, context):
    servico.confirmar_venda(event["compra_id"])
    return {"resultado": "VENDIDO"}


def liberar_reserva(event, context):
    motivo = event.get("motivo") or "PAGAMENTO_RECUSADO"
    servico.cancelar_compra(event["compra_id"], motivo)
    return {"resultado": "CANCELADA"}
