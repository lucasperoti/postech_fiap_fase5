import json
import time
import uuid

from botocore.exceptions import ClientError

from shared.auth import autorizar_admin
from shared.db import tabela
from shared.responses import created, error, ok

STATUS_VALIDOS_LISTAGEM = {"DISPONIVEL", "VENDIDO"}
CAMPOS_EDITAVEIS = {"marca", "modelo", "ano", "cor"}


def chave_ordenacao(preco_centavos: int, veiculo_id: str) -> str:
    return f"PRECO#{preco_centavos:014d}#{veiculo_id}"


def _para_centavos(preco) -> int | None:
    try:
        centavos = round(float(preco) * 100)
    except (TypeError, ValueError):
        return None
    return centavos if centavos > 0 else None


def _item_resposta(item: dict) -> dict:
    return {
        "id": item["PK"].removeprefix("VEICULO#"),
        "marca": item["marca"],
        "modelo": item["modelo"],
        "ano": item["ano"],
        "cor": item["cor"],
        "preco": int(item["preco_centavos"]) / 100,
        "status": item["status"],
        "criado_em": item.get("criado_em"),
    }


def criar_veiculo(event, context):
    erro = autorizar_admin(event)
    if erro:
        return erro
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error(400, "JSON_INVALIDO", "Corpo da requisição não é um JSON válido")

    faltantes = [c for c in ("marca", "modelo", "ano", "cor", "preco") if dados.get(c) in (None, "")]
    if faltantes:
        return error(422, "VALIDACAO", f"Campos obrigatórios ausentes: {', '.join(faltantes)}")
    centavos = _para_centavos(dados["preco"])
    if centavos is None:
        return error(422, "VALIDACAO", "preço deve ser um número positivo")
    if not isinstance(dados["ano"], int) or dados["ano"] < 1900:
        return error(422, "VALIDACAO", "ano inválido")

    veiculo_id = str(uuid.uuid4())
    agora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    item = {
        "PK": f"VEICULO#{veiculo_id}",
        "marca": dados["marca"],
        "modelo": dados["modelo"],
        "ano": dados["ano"],
        "cor": dados["cor"],
        "preco_centavos": centavos,
        "status": "DISPONIVEL",
        "GSI1PK": "STATUS#DISPONIVEL",
        "GSI1SK": chave_ordenacao(centavos, veiculo_id),
        "criado_em": agora,
    }
    tabela("VEICULOS_TABLE").put_item(Item=item)
    return created(_item_resposta(item))


def editar_veiculo(event, context):
    erro = autorizar_admin(event)
    if erro:
        return erro
    veiculo_id = event.get("pathParameters", {}).get("id")
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error(400, "JSON_INVALIDO", "Corpo da requisição não é um JSON válido")

    veiculos = tabela("VEICULOS_TABLE")
    chave = {"PK": f"VEICULO#{veiculo_id}"}
    try:
        item = veiculos.get_item(Key=chave)["Item"]
    except KeyError:
        return error(404, "NAO_ENCONTRADO", "Veículo não encontrado")

    for campo in CAMPOS_EDITAVEIS & dados.keys():
        if dados[campo] in (None, ""):
            return error(422, "VALIDACAO", f"{campo} não pode ser vazio")
        item[campo] = dados[campo]
    if "preco" in dados:
        centavos = _para_centavos(dados["preco"])
        if centavos is None:
            return error(422, "VALIDACAO", "preço deve ser um número positivo")
        item["preco_centavos"] = centavos

    item["GSI1SK"] = chave_ordenacao(item["preco_centavos"], item["PK"].removeprefix("VEICULO#"))
    try:
        veiculos.put_item(Item=item)
    except ClientError as exc:
        return error(500, "ERRO_INTERNO", str(exc))
    return ok(_item_resposta(item))


def listar_veiculos(event, context):
    params = event.get("queryStringParameters") or {}
    status = params.get("status", "DISPONIVEL").upper()
    if status not in STATUS_VALIDOS_LISTAGEM:
        return error(422, "VALIDACAO", "status deve ser DISPONIVEL ou VENDIDO")

    veiculos = tabela("VEICULOS_TABLE")
    resposta = veiculos.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :s",
        ExpressionAttributeValues={":s": f"STATUS#{status}"},
    )
    itens = sorted(resposta.get("Items", []), key=lambda i: i["GSI1SK"])
    return ok({"veiculos": [_item_resposta(i) for i in itens]})
