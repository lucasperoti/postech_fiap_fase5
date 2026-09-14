import json
import os

from shared.aws import cliente_aws
from shared.db import tabela
from shared.responses import error, ok

RESULTADOS_VALIDOS = {"APROVADO", "RECUSADO"}


def _header(event, nome: str) -> str | None:
    for chave, valor in (event.get("headers") or {}).items():
        if chave.lower() == nome:
            return valor
    return None


def _segredo_valido(header_segredo: str | None) -> bool:
    if not header_segredo:
        return False
    resposta = cliente_aws("secretsmanager").get_secret_value(
        SecretId=os.environ["WEBHOOK_SECRET_ARN"]
    )
    segredo = json.loads(resposta["SecretString"])["segredo"]
    return header_segredo == segredo


def processar_webhook(event, context):
    if not _segredo_valido(_header(event, "x-webhook-secret")):
        return error(401, "SEGREDO_INVALIDO", "Segredo do webhook inválido ou ausente")
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error(400, "JSON_INVALIDO", "Corpo da requisição não é um JSON válido")
    compra_id, resultado = dados.get("compra_id"), dados.get("resultado")
    if not compra_id or resultado not in RESULTADOS_VALIDOS:
        return error(422, "VALIDACAO", "compra_id e resultado (APROVADO|RECUSADO) são obrigatórios")

    compra = tabela("COMPRAS_TABLE").get_item(Key={"PK": f"COMPRA#{compra_id}"}).get("Item")
    if not compra:
        return error(404, "NAO_ENCONTRADO", "Compra não encontrada")
    if compra["estado"] != "AGUARDANDO_PAGAMENTO":
        return error(409, "ESTADO_INVALIDO", "A compra não está aguardando pagamento")
    task_token = compra.get("task_token")
    if not task_token:
        return error(409, "SAGA_NAO_AGUARDANDO", "A SAGA ainda não está aguardando o pagamento")

    sf = cliente_aws("stepfunctions")
    if resultado == "APROVADO":
        sf.send_task_success(
            taskToken=task_token,
            output=json.dumps({"compra_id": compra_id, "resultado": "APROVADO"}),
        )
    else:
        sf.send_task_failure(taskToken=task_token, error="PAGAMENTO_RECUSADO")
    return ok({"processado": True, "compra_id": compra_id, "resultado": resultado})
