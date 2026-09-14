import os

from shared.auth import autorizar_admin, claims_da_requisicao, resolver_cliente_id


def _evento_com_claims(claims):
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


def test_sem_authorizer_retorna_none():
    assert claims_da_requisicao({"requestContext": {}}) is None


def test_extrai_claims():
    claims = {"sub": "abc-123", "cognito:groups": ["admin"]}
    assert claims_da_requisicao(_evento_com_claims(claims)) == claims


def test_resolver_cliente_id_por_claims(aws_mock, env_vars, tabelas):
    clientes = tabelas[os.environ["CLIENTES_TABLE"]]
    clientes.put_item(Item={"PK": "CLIENTE#c1", "cognito_sub": "abc-123", "status": "ATIVO"})
    cliente_id, erro = resolver_cliente_id(_evento_com_claims({"sub": "abc-123"}), clientes)
    assert cliente_id == "c1"
    assert erro is None


def test_resolver_cliente_id_header_fallback_quando_sem_claims(aws_mock, env_vars):
    cliente_id, erro = resolver_cliente_id(
        {"requestContext": {}, "headers": {"x-cliente-id": "c9"}}, None
    )
    assert cliente_id == "c9"
    assert erro is None


def test_autorizar_admin_sem_claims_rejeita():
    assert autorizar_admin({"requestContext": {}})["statusCode"] == 403


def test_autorizar_admin_com_grupo(aws_mock, env_vars):
    assert autorizar_admin(_evento_com_claims({"cognito:groups": ["admin"]})) is None


def test_autorizar_admin_sem_grupo_rejeita():
    assert autorizar_admin(_evento_com_claims({"sub": "x"}))["statusCode"] == 403
