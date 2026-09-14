import os
import time

from botocore.exceptions import ClientError

from compras.servico import cancelar_compra
from shared.aws import cliente_aws
from shared.db import tabela

TTL_MINUTOS_PADRAO = 30


def expirar_reservas(event, context):
    """Cancela compras aguardando pagamento há mais de TTL_RESERVA_MINUTOS (padrão 30).

    Envia SendTaskFailure para a SAGA quando há token, mas tolera a falha dessa
    chamada: a compensação local (cancelar_compra) é a fonte da verdade do
    estado final, então a função é segura de reexecutar.
    """
    ttl = int(os.environ.get("TTL_RESERVA_MINUTOS", TTL_MINUTOS_PADRAO))
    corte = int(time.time()) - ttl * 60
    compras = tabela("COMPRAS_TABLE")
    resposta = compras.scan(
        FilterExpression="estado = :e AND reservado_ts < :corte",
        ExpressionAttributeValues={":e": "AGUARDANDO_PAGAMENTO", ":corte": corte},
    )
    expiradas = 0
    sf = cliente_aws("stepfunctions")
    for item in resposta.get("Items", []):
        compra_id = item["PK"].removeprefix("COMPRA#")
        token = item.get("task_token")
        if token:
            try:
                sf.send_task_failure(taskToken=token, error="RESERVA_EXPIRADA")
            except ClientError:
                pass
        cancelar_compra(compra_id, "EXPIRADA")
        expiradas += 1
    return {"expiradas": expiradas}
