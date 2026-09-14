from shared.responses import error


def _headers_normalizados(event) -> dict:
    return {k.lower(): v for k, v in (event.get("headers") or {}).items()}


def claims_da_requisicao(event) -> dict | None:
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    if "jwt" in authorizer:  # API Gateway HTTP API (v2)
        return authorizer["jwt"].get("claims")
    return authorizer.get("claims")  # API Gateway REST API (v1) com authorizer Cognito


def resolver_cliente_id(event, clientes_table) -> tuple[str | None, dict | None]:
    claims = claims_da_requisicao(event)
    if claims:
        sub = claims.get("sub")
        if not clientes_table or not sub:
            return None, error(401, "NAO_AUTENTICADO", "Identidade do cliente não encontrada")
        resposta = clientes_table.query(
            IndexName="GSI1",
            KeyConditionExpression="cognito_sub = :sub",
            ExpressionAttributeValues={":sub": sub},
        )
        itens = resposta.get("Items", [])
        if not itens or itens[0].get("status") != "ATIVO":
            return None, error(403, "CLIENTE_INATIVO", "Cliente não encontrado ou inativo")
        return itens[0]["PK"].removeprefix("CLIENTE#"), None
    cliente_id = _headers_normalizados(event).get("x-cliente-id")
    if cliente_id:
        return cliente_id, None
    return None, error(401, "NAO_AUTENTICADO", "Autenticação necessária")


def autorizar_admin(event) -> dict | None:
    claims = claims_da_requisicao(event)
    grupos = (claims or {}).get("cognito:groups", [])
    if claims and "admin" in grupos:
        return None
    headers = _headers_normalizados(event)
    if not claims and headers.get("x-admin") == "true":
        return None  # somente quando o authorizer está desligado (EnableAuth=false)
    return error(403, "ACESSO_NEGADO", "Apenas administradores podem executar esta ação")
